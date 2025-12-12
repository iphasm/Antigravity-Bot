import time
import os
import threading
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import logging
import platform
import sys
import requests
from dotenv import load_dotenv

# Importar módulos internos
from data.fetcher import get_market_data

# Global Config Imports (Fix for Handlers)
from antigravity_quantum.config import ENABLED_STRATEGIES, DISABLED_ASSETS

from strategies.engine import StrategyEngine
from strategies.engine import StrategyEngine
from utils.trading_manager import SessionManager
from utils.trading_manager import SessionManager
from utils.personalities import PersonalityManager
from utils.system_state_manager import SystemStateManager # NEW

# Personality & State Engine
personality_manager = PersonalityManager()
state_manager = SystemStateManager() # NEW Initialize State Manager

# Cargar variables de entorno
load_dotenv()

# Logger de Telebot
logger = telebot.logger
telebot.logger.setLevel(logging.INFO)

# Configuración de Proxy para Telegram (Si existe en el sistema)
# Prioridad: PROXY_URL (Railway) > HTTPS_PROXY > HTTP_PROXY
sys_proxy = os.getenv('PROXY_URL') or os.getenv('HTTPS_PROXY') or os.getenv('HTTP_PROXY')
if sys_proxy:
    from telebot import apihelper
    apihelper.proxy = {'https': sys_proxy}
    print(f"🌍 Proxy detectado para Telegram: {sys_proxy}")


# --- CONFIGURACIÓN DE ACTIVOS Y GRUPOS ---
ASSET_GROUPS = {
    'CRYPTO': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'ADAUSDT', 'LTCUSDT', 'LINKUSDT', 'DOGEUSDT', 'AVAXUSDT', 'ZECUSDT', 'SUIUSDT'],
    'STOCKS': ['TSLA', 'NVDA', 'MSFT', 'AAPL', 'AMD'],
    'COMMODITY': ['GLD', 'USO'] # ETFs for Alpaca (Gold, Oil)
}

# Mapping de nombres amigables
TICKER_MAP = {
    'BTCUSDT': 'Bitcoin',
    'ETHUSDT': 'Ethereum',
    'SOLUSDT': 'Solana',
    'BNBUSDT': 'Binance Coin',
    'XRPUSDT': 'Ripple',
    'ADAUSDT': 'Cardano',
    'LTCUSDT': 'Litecoin',
    'LINKUSDT': 'Chainlink',
    'DOGEUSDT': 'Dogecoin',
    'AVAXUSDT': 'Avalanche',
    'ZECUSDT': 'Zcash',
    'SUIUSDT': 'Sui',
    'TSLA': 'Tesla',
    'NVDA': 'NVIDIA',
    'MSFT': 'Microsoft',
    'AAPL': 'Apple',
    'AMD': 'AMD',
    'GLD': 'Gold (ETF)',
    'USO': 'Oil (ETF)'
}

# Estado de los Grupos (Switch ON/OFF)
GROUP_CONFIG = {
    'CRYPTO': True,
    'STOCKS': True,
    'COMMODITY': True
}

# Configuración de Señales
SIGNAL_COOLDOWN = 900 # 15 Minutos por defecto
last_alert_times = {} # {asset: timestamp}
pos_state = {} # {asset: 'NEUTRAL' | 'LONG'} - Para evitar spam de salidas

TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_ADMIN_ID = os.getenv('TELEGRAM_ADMIN_ID')
TELEGRAM_CHAT_IDS = [id.strip() for id in os.getenv('TELEGRAM_CHAT_ID', '').split(',') if id.strip()]

# Inicializar Bot
bot = None
session_manager = None 

if TELEGRAM_TOKEN:
    bot = telebot.TeleBot(TELEGRAM_TOKEN)
else:
    print("ADVERTENCIA: No se encontró TELEGRAM_TOKEN.")
# --- DECORADORES HELPER ---

def threaded_handler(func):
    """
    Decorador para ejecutar el handler en un hilo separado.
    Evita que operaciones largas (API calls) bloqueen al bot.
    """
    def wrapper(message, *args, **kwargs):
        # Creamos el thread
        thread = threading.Thread(target=func, args=(message,) + args, kwargs=kwargs)
        thread.daemon = True # El hilo muere si el programa principal muere
        thread.start()
    return wrapper

def resolve_symbol(text):
    """Limpia y estandariza el símbolo (input). Agrega 'USDT' automáticamente."""
    # FIX: Remove common separators
    s = text.strip().upper().replace('/', '').replace('-', '').replace('_', '')
    
    # 1. Exact Match Check (Groups or Map keys)
    known_assets = []
    for g in ASSET_GROUPS.values():
        known_assets.extend(g)
    
    if s in known_assets or s in TICKER_MAP:
        return s
        
    # 2. Reverse Lookup (Name -> Ticker)
    # Checks if input matches a friendly name in TICKER_MAP (e.g. "TESLA" -> "TSLA")
    for ticker, name in TICKER_MAP.items():
        if s == name.upper():
            return ticker
            
    # 3. Try Appending USDT (Common Crypto case)
    # If user types "BTC", checking "BTCUSDT"
    s_usdt = s + "USDT"
    if s_usdt in ASSET_GROUPS.get('CRYPTO', []) or s_usdt in TICKER_MAP:
        return s_usdt
        
    return s

def process_asset(asset):
    """
    Función helper unificada para procesar un activo.
    Usada tanto por /price (reporte) como por el Trading Loop (señales).
    Devuelve: (Success: bool, Data: dict|str)
    """
    try:
        from antigravity_quantum.config import DISABLED_ASSETS
        if asset in DISABLED_ASSETS:
            return False, "Asset in Blacklist"

        # 1. Obtener Datos (Micro - 15m)
        df = get_market_data(asset, timeframe='15m', limit=200)
        if df.empty: 
            return False, "No Data"
        
        # 2. Análisis Micro (Spot + Futuros)
        engine = StrategyEngine(df)
        res = engine.analyze()
        
        # --- 3. LAZY FETCHING (MTF - 1H) ---
        # Solo gastamos API si hay señal potencial
        has_signal = res['signal_spot'] or (res['signal_futures'] not in ['WAIT', 'EXIT_ALL', 'CLOSE_LONG', 'CLOSE_SHORT'])
        
        if has_signal:
            try:
                # Descargar Tendencia Macro (1H)
                df_macro = get_market_data(asset, timeframe='1H', limit=200)
                trend_1h = engine.analyze_macro_trend(df_macro)
                
                # Reglas de Filtrado MTF
                # Long solo en tendencia BULL/NEUTRAL (Evita Bear)
                # Short solo en tendencia BEAR/NEUTRAL (Evita Bull)
                
                current_fut = res['signal_futures']
                
                if current_fut == 'BUY' and trend_1h == 'BEAR':
                    res['signal_futures'] = 'WAIT'
                    res['reason_futures'] = f"⛔ FILTRADO MTF: Señal Long en Tendencia 1H Bajista ({trend_1h})"
                    
                elif current_fut == 'SHORT' and trend_1h == 'BULL':
                    res['signal_futures'] = 'WAIT'
                    res['reason_futures'] = f"⛔ FILTRADO MTF: Señal Short en Tendencia 1H Alcista ({trend_1h})"
                else:
                    # Append MTF info to reason
                    res['reason_futures'] += f" [MTF: {trend_1h}]"

            except Exception as e:
                print(f"MTF Error for {asset}: {e}")
        
        return True, res
        
    except Exception as e:
        return False, str(e)

def send_alert(message):
    """Transmite el mensaje a todos los destinos configurados"""
    targets = set(TELEGRAM_CHAT_IDS)
    if session_manager:
        for s in session_manager.get_all_sessions():
            targets.add(s.chat_id)
            
    if bot and targets:
        for chat_id in targets:
            try:
                bot.send_message(chat_id, message, parse_mode='Markdown')
            except Exception as e:
                print(f"Error enviando alerta a {chat_id}: {e}")
    else:
        print(f"ALERTA (Log): {message}")

@threaded_handler
def handle_price(message):
    try:
        sent = bot.reply_to(message, "⏳ *Escaneando mercado...* (Esto no bloquea el bot)", parse_mode='Markdown')
        
        report = "📡 *RADAR DE MERCADO (SPOT + FUTUROS)*\n\n"
        
        # Check Groups
        active_groups = [g for g, active in GROUP_CONFIG.items() if active]
        if not active_groups:
            bot.edit_message_text("⚠️ Todos los grupos están desactivados. Usa `/toggle_group`.", chat_id=sent.chat.id, message_id=sent.message_id)
            return

        for group_name in active_groups:
            # Format Group Name: Remove underscores, Bold
            display_name = group_name.replace('_', ' ')
            assets = ASSET_GROUPS.get(group_name, [])
            report += f"*{display_name}*\n"
            
            for asset in assets:
                try:
                    success, res = process_asset(asset)
                    
                    if not success:
                        # Sanitize error
                        safe_err = str(res).replace('`', "'").replace('_', ' ')
                        friendly_name = TICKER_MAP.get(asset, asset)
                        report += f"• {friendly_name}: ❌ Err: `{safe_err}`\n"
                        continue
                    
                    # Unpack metrics
                    m = res['metrics']
                    spot_sig = res['signal_spot']
                    fut_sig = res['signal_futures']
                    
                    # Iconos
                    sig_icon = ""
                    if spot_sig: sig_icon += "💎 SPOT "
                    if fut_sig == 'BUY': sig_icon += "🚀 LONG "
                    elif fut_sig == 'CLOSE_LONG': sig_icon += "📉 CLOSE "
                    
                    friendly_name = TICKER_MAP.get(asset, asset)
                    entry = f"• {friendly_name}: ${m['close']:,.2f} | RSI: {m['rsi']:.1f} {sig_icon}\n"
                    report += entry
                except Exception as inner_e:
                    print(f"Error con asset {asset}: {inner_e}")
                    continue
            
            report += "\n"
            
        bot.edit_message_text(report, chat_id=sent.chat.id, message_id=sent.message_id, parse_mode='Markdown')
    except Exception as e:
        print(f"Error crítico en /price: {e}")
        # Intentar enviar en texto plano si falla Markdown
        if 'sent' in locals() and sent:
            try:
                bot.edit_message_text(f"❌ Error generando reporte (Markdown fallido):\n\n{report}", chat_id=sent.chat.id, message_id=sent.message_id)
            except:
                pass
        else:
            bot.reply_to(message, f"❌ Error Fatal: {str(e)}")


# --- MANUAL TRADING HANDLERS ---

@threaded_handler
def handle_manual_short(message):
    """ /short <SYMBOL> """
    chat_id = str(message.chat.id)
    session = session_manager.get_session(chat_id)
    if not session:
        bot.reply_to(message, "⚠️ No tienes sesión activa. Usa /set_keys.")
        return

    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "⚠️ Uso: `/short <SYMBOL>` (Ej: ETHUSDT)")
            return
            
        symbol = resolve_symbol(parts[1])
        bot.reply_to(message, f"⏳ Analizando {symbol} (ATR) y Ejecutando SHORT...")
        
        # 1. Get ATR
        atr_val = None
        success, res = process_asset(symbol)
        if success and 'metrics' in res:
            atr_val = res['metrics'].get('atr', None)
        
        # 2. Execute
        success, msg = session.execute_short_position(symbol, atr=atr_val)
        
        if success:
            pos_state[symbol] = 'SHORT'
            bot.reply_to(message, f"✅ *SHORT EJECUTADO*\n{msg}", parse_mode='Markdown')
        else:
            bot.reply_to(message, f"❌ Error: {msg}")

    except Exception as e:
        bot.reply_to(message, f"❌ Error crítico: {e}")

@threaded_handler
def handle_manual_long(message):
    """ /long <SYMBOL> """
    chat_id = str(message.chat.id)
    session = session_manager.get_session(chat_id)
    if not session:
        bot.reply_to(message, "⚠️ No tienes sesión activa. Usa /set_keys.")
        return

    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "⚠️ Uso: `/long <SYMBOL>` (Ej: BTCUSDT)")
            return
            
        symbol = resolve_symbol(parts[1])
        bot.reply_to(message, f"⏳ Analizando {symbol} (ATR) y Ejecutando LONG...")
        
        # 1. Get ATR
        atr_val = None
        success, res = process_asset(symbol)
        if success and 'metrics' in res:
            atr_val = res['metrics'].get('atr', None)
        
        # 2. Execute
        success, msg = session.execute_long_position(symbol, atr=atr_val)
        
        if success:
            pos_state[symbol] = 'LONG'
            bot.reply_to(message, f"✅ *LONG EJECUTADO*\n{msg}", parse_mode='Markdown')
        else:
            bot.reply_to(message, f"❌ Error: {msg}")

    except Exception as e:
        bot.reply_to(message, f"❌ Error crítico: {e}")

@threaded_handler
def handle_manual_sell(message):
    """ /sell <SYMBOL> (Smart Sell: Close Long OR Open Short) """
    chat_id = str(message.chat.id)
    session = session_manager.get_session(chat_id)
    if not session:
        bot.reply_to(message, "⚠️ No tienes sesión activa. Usa /set_keys.")
        return

    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "⚠️ Uso: `/sell <SYMBOL>`")
            return
            
        symbol = resolve_symbol(parts[1])
        
        # 1. Check Active Positions
        active_positions = session.get_active_positions()
        has_pos = False
        pos_amt = 0.0
        
        for p in active_positions:
            if p['symbol'] == symbol:
                has_pos = True
                pos_amt = float(p.get('amt', 0))
                break
        
        # Logic: If Long (>0) -> Close. Else -> Short.
        if has_pos and pos_amt > 0:
            bot.reply_to(message, f"📉 Cerrando LONG existente en {symbol}...")
            success, msg = session.execute_close_position(symbol)
            if success: pos_state[symbol] = 'NEUTRAL'
            bot.reply_to(message, f"{msg}")
        else:
            bot.reply_to(message, f"⏳ Analizando {symbol} (ATR) y Ejecutando SHORT...")
            
            # 1. Get ATR
            atr_val = None
            success, res = process_asset(symbol)
            if success and 'metrics' in res:
                atr_val = res['metrics'].get('atr', None)

            # 2. Execute
            success, msg = session.execute_short_position(symbol, atr=atr_val)
            if success:
                pos_state[symbol] = 'SHORT'
                bot.reply_to(message, f"✅ *SHORT EJECUTADO*\n{msg}", parse_mode='Markdown')
            else:
                bot.reply_to(message, f"❌ Error: {msg}")
                
    except Exception as e:
         bot.reply_to(message, f"❌ Error crítico: {e}")

@threaded_handler
def handle_manual_close(message):
    """ /close <SYMBOL> """
    chat_id = str(message.chat.id)
    session = session_manager.get_session(chat_id)
    if not session: 
        bot.reply_to(message, "⚠️ No tienes sesión activa. Usa /set_keys.")
        return

    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "⚠️ Uso: `/close <SYMBOL>`")
            return
        
        symbol = resolve_symbol(parts[1])
        success, msg = session.execute_close_position(symbol)
        if success: pos_state[symbol] = 'NEUTRAL'
        bot.reply_to(message, msg)
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")

@threaded_handler
def handle_manual_closeall(message):
    """ /closeall """
    chat_id = str(message.chat.id)
    session = session_manager.get_session(chat_id)
    if not session: 
        bot.reply_to(message, "⚠️ No tienes sesión activa. Usa /set_keys.")
        return
    
    bot.reply_to(message, "🚨 Ejecutando CLOSE ALL...")
    success, msg = session.execute_close_all()
    bot.reply_to(message, msg)

# --- AUTOMATION CONTROLS ---

def handle_mode_switch(message, mode):
    chat_id = str(message.chat.id)
    session = session_manager.get_session(chat_id)
    if not session:
        bot.reply_to(message, "⚠️ Sin sesión activa. Usa /set_keys primero.")
        return
        
    # Get Current Personality
    p_key = session.config.get('personality', 'NEXUS')

    if session.set_mode(mode):
        session_manager.save_sessions()
        
        # Dynamic Message
        msg_type = f"{mode}_ON" # PILOT_ON, COPILOT_ON, WATCHER_ON
        msg = personality_manager.get_message(p_key, msg_type)
        
        bot.reply_to(message, msg, parse_mode='Markdown')
    else:
        bot.reply_to(message, "❌ Error cambiando modo.")

def handle_get_mode(message):
    chat_id = str(message.chat.id)
    session = session_manager.get_session(chat_id)
    if not session: return
    
    mode = session.config.get('mode', 'WATCHER')
    bot.reply_to(message, f"🎮 Modo Actual: **{mode}**", parse_mode='Markdown')





# --- RESTORED HANDLERS ---



# ... (handle_risk, handle_strategy logic inserted below, handled in previous tool)


def handle_risk(message):
    """Explication detallada de la gestión de riesgo activa"""
    chat_id = str(message.chat.id)
    session = session_manager.get_session(chat_id)
    
    lev = session.config.get('leverage', 5) if session else 5
    cap = session.config.get('max_capital_pct', 0.10) * 100 if session else 10
    sl = session.config.get('stop_loss_pct', 0.02) * 100 if session else 2
    
    msg = (
        "🛡️ **PROTOCOLO DE GESTIÓN DE RIESGO**\n\n"
        f"• **Capital por Op:** `{cap:.1f}%` de la cuenta total.\n"
        f"• **Apalancamiento:** `{lev}x` (Isolated).\n"
        f"• **Stop Loss Base:** `{sl:.1f}%` (Fijo) o `2x ATR` (Dinámico).\n"
        "• **Circuit Breaker:** 🛑 Se detiene tras 3 pérdidas consecutivas.\n\n"
        "💡 _El sistema ajusta el tamaño de la posición basado en la volatilidad del activo (ATR) para mantener el riesgo constante._"
    )
    bot.reply_to(message, msg, parse_mode='Markdown')

@bot.message_handler(commands=['strategy'])
def handle_strategy(message):
    """Explicación de la estrategia según personalidad"""
    chat_id = str(message.chat.id)
    session = session_manager.get_session(chat_id)
    p_key = session.config.get('personality', 'STANDARD_ES') if session else 'STANDARD_ES'
    
    msg = personality_manager.get_message(p_key, 'STRATEGY_MSG')
    bot.reply_to(message, msg, parse_mode='Markdown')

@bot.message_handler(commands=['about', 'info'])
def handle_about(message):
    """Resumen del bot según personalidad"""
    chat_id = str(message.chat.id)
    session = session_manager.get_session(chat_id)
    p_key = session.config.get('personality', 'STANDARD_ES') if session else 'STANDARD_ES'
    
    msg = personality_manager.get_message(p_key, 'ABOUT_MSG')
    bot.reply_to(message, msg, parse_mode='Markdown')




def get_fear_and_greed_index():
    """Fetch Fear and Greed Index from alternative.me"""
    try:
        url = "https://api.alternative.me/fng/"
        resp = requests.get(url, timeout=5)
        data = resp.json()
        if 'data' in data and len(data['data']) > 0:
            item = data['data'][0]
            val = int(item['value'])
            classification = item['value_classification']
            
            # Icon Logic
            icon = "😐"
            if val >= 75: icon = "🤑" # Extreme Greed
            elif val >= 55: icon = "😏" # Greed
            elif val <= 25: icon = "😱" # Extreme Fear
            elif val <= 45: icon = "😨" # Fear
            
            return f"{icon} *{classification}* ({val}/100)"
    except Exception as e:
        print(f"F&G Error: {e}")
    
    return "N/A"

@threaded_handler
def handle_status(message):
    """Muestra estado del sistema (Read Only)"""
    chat_id = str(message.chat.id)
    session = session_manager.get_session(chat_id)
    
    # Defaults
    mode = "WATCHER"
    has_keys = False
    
    if session:
        cfg = session.get_configuration()
        mode = cfg.get('mode', 'WATCHER')
        has_keys = cfg['has_keys']
    
    fg = get_fear_and_greed_index()
    p_key = session.config.get('personality', 'NEXUS') if session else 'NEXUS'
    
    header = personality_manager.get_message(p_key, 'STATUS_HEADER')
    footer = personality_manager.get_message(p_key, 'STATUS_FOOTER')

    status = f"{header}\n"
    status += f"🛡️ *Modo:* `{mode}`\n"
    status += f"🧠 *Sentimiento:* {fg}\n"
    status += f"🔌 *Conexión:* {'✅ OK' if has_keys else '❌ OFF'}\n"
    
    status += "\n📡 *Radares Activos:*\n"
    for group, enabled in GROUP_CONFIG.items():
        icon = "🟢" if enabled else "🔴"
        name = group.replace('_', ' ')
        count = len(ASSET_GROUPS.get(group, [])) if enabled else 0
        status += f"{icon} {name} ({count})\n"
        
    status += f"\n{footer}"
    bot.reply_to(message, status, parse_mode='Markdown')

@bot.message_handler(commands=['config'])
def handle_config(message):
    """Panel de Configuración Interactiva"""
    cid = message.chat.id
    session = session_manager.get_session(str(cid))
    
    # Values
    lev = session.config.get('leverage', 5) if session else 5
    margin = session.config.get('max_capital_pct', 0.1) * 100 if session else 10
    
    markup = InlineKeyboardMarkup(row_width=2)
    # Toggles
    markup.add(
        InlineKeyboardButton("🎛️ Estrategias", callback_data="CMD|/strategies"),
        InlineKeyboardButton("📡 Grupos", callback_data="CMD|/togglegroup")
    )
    # Assets
    markup.add(InlineKeyboardButton("🪙 Activos (Blacklist)", callback_data="CMD|/assets"))
    
    # Params
    markup.add(
        InlineKeyboardButton(f"⚖️ Lev: {lev}x", callback_data="CFG|LEV_MENU"),
        InlineKeyboardButton(f"💰 Margin: {margin:.0f}%", callback_data="CFG|MARGIN_MENU")
    )
    # Personality
    markup.add(InlineKeyboardButton("🧠 Personalidad", callback_data="CMD|/personality"))
    
    bot.reply_to(message, "⚙️ **PANEL DE CONTROL**\nSelecciona qué deseas ajustar:", reply_markup=markup, parse_mode='Markdown')

@bot.message_handler(commands=['togglegroup'])
def handle_toggle_group(message):
    """Selector Interactivo de Grupos"""
    markup = InlineKeyboardMarkup()
    for group, enabled in GROUP_CONFIG.items():
        state = "✅" if enabled else "❌"
        markup.add(InlineKeyboardButton(f"{state} {group}", callback_data=f"TOGGLEGRP|{group}"))
        
    bot.reply_to(message, "📡 **CONFIGURACIÓN DE RADARES**\nActiva/Desactiva grupos de mercado:", reply_markup=markup, parse_mode='Markdown')

from antigravity_quantum.config import DISABLED_ASSETS

@bot.message_handler(commands=['assets', 'toggleassets'])
def handle_assets(message):
    """Selector de Activos Individuales (Blacklist/Whitelist)"""
    cid = message.chat.id
    
    # Gather all assets from ENABLED groups ONLY
    active_assets = []
    for group, enabled in GROUP_CONFIG.items():
        if enabled:
            active_assets.extend(ASSET_GROUPS.get(group, []))
            
    if not active_assets:
        bot.reply_to(message, "⚠️ No hay grupos activos. Usa /togglegroup primero.")
        return
    
    markup = InlineKeyboardMarkup(row_width=3)
    buttons = []
    
    # Limit 50 to avoid big payload error
    for asset in active_assets[:50]: 
        is_disabled = asset in DISABLED_ASSETS
        icon = "❌" if is_disabled else "✅"
        # callback: TOGGLEASSET|BTCUSDT
        buttons.append(InlineKeyboardButton(f"{icon} {asset}", callback_data=f"TOGGLEASSET|{asset}"))
        
    markup.add(*buttons)
    bot.reply_to(message, "🪙 **CONTROL DE ACTIVOS**\n(✅ = Activo / ❌ = Ignorado)\n_Toque para alternar_", reply_markup=markup, parse_mode='Markdown')

@bot.message_handler(commands=['resetpilot', 'reset_pilot'])
def handle_reset_pilot(message):
    """Reinicia el contador del Circuit Breaker"""
    chat_id = str(message.chat.id)
    session = session_manager.get_session(chat_id)
    if not session: 
        bot.reply_to(message, "⚠️ No tienes sesión activa. Usa /set_keys.")
        return

    # Call method (will be added to utils next)
    try:
        session.reset_circuit_breaker()
        bot.reply_to(message, "✅ **Circuit Breaker Reiniciado**.\nEl contador de pérdidas consecutivas se ha restablecido a 0.\nPuedes reactivar `/pilot` si lo deseas.", parse_mode='Markdown')
    except AttributeError:
        bot.reply_to(message, "❌ Error: Método reset_circuit_breaker no encontrado en TradingSession (Actualizando código...).")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")

@bot.message_handler(commands=['set_interval', 'setinterval'])
def handle_set_interval(message):
    """Ajusta el cooldown global en minutos"""
    global SIGNAL_COOLDOWN
    try:
        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message, "⚠️ Uso: `/set_interval <minutos>`")
            return
            
        minutes = int(args[1])
        if minutes < 1:
            bot.reply_to(message, "❌ Mínimo 1 minuto.")
            return
            
        SIGNAL_COOLDOWN = minutes * 60
        bot.reply_to(message, f"⏱️ Frecuencia de señal ajustada a **{minutes} minutos**.")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")

    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")

@threaded_handler
@bot.message_handler(commands=['set_keys', 'setkeys'])
def handle_set_keys(message):
    """Configura API Keys: /set_keys <KEY> <SECRET>"""
    chat_id = str(message.chat.id)
    try:
        args = message.text.split()
        if len(args) != 3:
            bot.reply_to(message, "⚠️ Uso: `/set_keys <API_KEY> <API_SECRET>`\n(Te recomendamos borrar el mensaje después)", parse_mode='Markdown')
            return
            
        key = args[1].strip()
        secret = args[2].strip()
        
        # Guardar en SessionManager
        session = session_manager.create_or_update_session(chat_id, key, secret)
        
        status = "✅ *API Keys Configuradas Correctamente.*\n"
        if session.client:
            status += "🔌 Conexión con Binance: *ESTABLE*"
        else:
            status += "⚠️ Keys guardadas pero *falló la conexión* (Revisa si son correctas)."
            
        bot.reply_to(message, status, parse_mode='Markdown')
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")

@threaded_handler
def handle_debug(message):
    """ Genera un Reporte de Diagnóstico del Sistema """
    sent = bot.reply_to(message, "🔍 Ejecutando diagnóstico de sistema...")
    chat_id = str(message.chat.id)
    session = session_manager.get_session(chat_id)
    
    # 1. System Info
    py_ver = platform.python_version()
    os_plat = platform.system()
    
    # 2. Credentials
    has_key = "✅" if session and session.api_key else "❌"
    has_sec = "✅" if session and session.api_secret else "❌"
    
    # 3. Network / IP
    proxy_conf = "Yes" if os.getenv('PROXY_URL') else "No"
    
    try:
        # Effective IP (Outgoing)
        ip_info = requests.get('http://ip-api.com/json', timeout=5).json()
        eff_ip = ip_info.get('query', 'Unknown')
        loc = f"{ip_info.get('country', 'Unknown')} ({ip_info.get('regionName', 'Unknown')})"
    except Exception as e:
        eff_ip = f"Error: {str(e)}"
        loc = "Unknown"

    loc_check = "✅" if "US" not in loc else "❌ RESTRICTED (US)"
    
    # Build
    pub_status = "Unknown"
    try:
        t0 = time.time()
        btc_data = get_market_data('BTCUSDT', limit=1)
        ping_ms = int((time.time() - t0) * 1000)
        if not btc_data.empty: pub_status = f"✅ Success ({ping_ms}ms)"
        else: pub_status = "⚠️ Data Empty"
    except Exception as e:
        pub_status = f"❌ Failed: {str(e)}"
            
    # Report Build
    report = (
        "🕵️ *DIAGNÓSTICO DEL SISTEMA*\n"
        "〰️〰️〰️〰️〰️〰️\n"
        f"🖥️ *OS:* {os_plat} | *Python:* {py_ver}\n"
        f"🌍 *IP Efectiva:* `{eff_ip}`\n"
        f"📍 *Ubicación:* `{loc}` {loc_check}\n"
        f"🔌 *Proxy Configurado:* {proxy_conf}\n\n"
        f"📊 *Data Fetch:* {pub_status}\n"
        f"🔑 *Keys:* {has_key}/{has_sec}"
    )
    
    bot.edit_message_text(report, chat_id=sent.chat.id, message_id=sent.message_id, parse_mode='Markdown')



@threaded_handler
@bot.message_handler(commands=['set_leverage', 'setleverage'])
def handle_set_leverage(message):
    """ /set_leverage - Interactive Menu """
    markup = InlineKeyboardMarkup()
    markup.row_width = 5
    markup.add(
        InlineKeyboardButton("5x", callback_data="CFG|LEV|5"),
        InlineKeyboardButton("10x", callback_data="CFG|LEV|10"),
        InlineKeyboardButton("20x", callback_data="CFG|LEV|20"),
        InlineKeyboardButton("50x", callback_data="CFG|LEV|50"),
        InlineKeyboardButton("100x", callback_data="CFG|LEV|100")
    )
    bot.reply_to(message, "⚖️ *Selecciona Apalancamiento Futuros:*", reply_markup=markup, parse_mode='Markdown')

@threaded_handler
@bot.message_handler(commands=['set_margin', 'setmargin'])
def handle_set_margin(message):
    """ /set_margin - Interactive Menu """
    markup = InlineKeyboardMarkup()
    markup.row_width = 4
    markup.add(
        InlineKeyboardButton("5%", callback_data="CFG|MARGIN|0.05"),
        InlineKeyboardButton("10%", callback_data="CFG|MARGIN|0.10"),
        InlineKeyboardButton("20%", callback_data="CFG|MARGIN|0.20"),
        InlineKeyboardButton("50%", callback_data="CFG|MARGIN|0.50")
    )
    bot.reply_to(message, "💰 *Selecciona Margen Máximo Global:*", reply_markup=markup, parse_mode='Markdown')

@threaded_handler
@bot.message_handler(commands=['buy'])
def handle_manual_buy_spot(message):
    """ /buy <SYMBOL> """
    chat_id = str(message.chat.id)
    session = session_manager.get_session(chat_id)
    if not session: 
        bot.reply_to(message, "⚠️ Configura tus llaves primero (/set_keys).")
        return

    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "⚠️ Uso: `/buy <SYMBOL>` (Ej: `/buy XRP`)")
            return
        
        symbol = resolve_symbol(parts[1])
        bot.reply_to(message, f"⏳ Ejecutando Compra Spot: {symbol}...")
        success, msg = session.execute_spot_buy(symbol)
        
        if success:
            bot.reply_to(message, f"✅ *COMPRA EXITOSA*\n{msg}", parse_mode='Markdown')
        else:
             bot.reply_to(message, f"❌ Falló Compra: {msg}")

    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")

    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")

@threaded_handler
@bot.message_handler(commands=['set_spot_allocation', 'setspotallocation'])
def handle_set_spot_allocation(message):
    markup = InlineKeyboardMarkup()
    markup.row_width = 4
    markup.add(
        InlineKeyboardButton("10%", callback_data="CFG|SPOT|0.10"),
        InlineKeyboardButton("20%", callback_data="CFG|SPOT|0.20"),
        InlineKeyboardButton("50%", callback_data="CFG|SPOT|0.50"),
        InlineKeyboardButton("100%", callback_data="CFG|SPOT|1.00")
    )
    bot.reply_to(message, "💎 *Selecciona Asignación SPOT (USDT Disponible):*", reply_markup=markup, parse_mode='Markdown')
@threaded_handler
def handle_wallet(message):
    """Muestra detalles completos de la cartera (Spot + Futuros)"""
    chat_id = str(message.chat.id)
    session = session_manager.get_session(chat_id)
    if not session: 
        bot.reply_to(message, "⚠️ Sin sesión activa. Usa /set_keys.")
        return
    
    bot.reply_to(message, "⏳ Consultando Blockchain y Binance...")
    
    try:
        details = session.get_wallet_details()
        if not details:
            bot.reply_to(message, "❌ Error obteniendo datos de cartera.")
            return
            
        # Unpack (Correct Keys)
        spot_bal = details.get('spot_usdt', 0.0)
        earn_bal = details.get('earn_usdt', 0.0)
        spot_total = spot_bal + earn_bal # Total Spot Value
        
        fut_bal = details.get('futures_balance', 0.0)
        fut_pnl = details.get('futures_pnl', 0.0)
        fut_total= details.get('futures_total', 0.0)
        alpaca_native = details.get('alpaca_equity', 0.0)
        
        net_worth = spot_total + fut_total + alpaca_native
        
        pnl_icon = "🟢" if fut_pnl >= 0 else "🔴"
        
        # Get Personality Header
        p_key = session.config.get('personality', 'STANDARD_ES')
        wallet_header = personality_manager.get_message(p_key, 'WALLET_HEADER')

        msg = (
            f"{wallet_header}\n"
            "〰️〰️〰️〰️〰️〰️\n"
            f"🏦 *SPOT (USDT):* `${spot_bal:,.2f}`\n"
            f"🐷 *EARN (Ahorros):* `${earn_bal:,.2f}`\n"
            "〰️〰️〰️〰️〰️〰️\n"
            f"🚀 *FUTUROS Balance:* `${fut_bal:,.2f}`\n"
            f"📊 *FUTUROS PnL:* {pnl_icon} `${fut_pnl:,.2f}`\n"
            f"💰 *FUTUROS Total:* `${fut_total:,.2f}`\n"
            "〰️〰️〰️〰️〰️〰️\n"
            f"🦙 *ALPACA (Stocks):* `${alpaca_native:,.2f}`\n"
            "〰️〰️〰️〰️〰️〰️\n"
            f"🏆 *NET WORTH TOTAL:* `${net_worth:,.2f}`"
        )
        
        bot.reply_to(message, msg, parse_mode='Markdown')
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")


# --- MASTER LISTENER ---
@bot.message_handler(func=lambda m: True)
def master_listener(message):
    """Recibe TODO y despacha"""
    try:
        text = message.text
        if not text: return
        
        # print(f"📨 DEBUG: Recibido '{text}' de {message.chat.id}")
        
        if text.startswith('/'):
            # 1. CLEAN COMMAND Parsing (/start@BotName -> /start)
            full_cmd = text.split()[0]
            if '@' in full_cmd:
                cmd_part = full_cmd.split('@')[0].lower()
            else:
                cmd_part = full_cmd.lower()
            
            user_id = str(message.chat.id)
            
            # --- RBAC LAYER ---
            role = 'PUBLIC'
            if user_id == TELEGRAM_ADMIN_ID:
                role = 'ADMIN'
            elif user_id in TELEGRAM_CHAT_IDS:
                role = 'SUBSCRIBER'
            
            # 1. PUBLIC ACCESS (Blocked except /id)
            if role == 'PUBLIC':
                if cmd_part == '/id':
                    bot.reply_to(message, f"🆔 Tu ID: `{user_id}`\n❌ No autorizado.", parse_mode='Markdown')
                else:
                    bot.reply_to(message, f"⛔ Acceso Denegado. ID: `{user_id}`\nContacta al Administrador.", parse_mode='Markdown')
                return
            
            # 2. SYSTEM COMMANDS (Admin Only)
            # /toggle_group, /set_interval, /debug
            SYSTEM_CMDS = ['/toggle_group', '/togglegroup', '/toggle', '/set_interval', '/setinterval', '/debug']
            if cmd_part in SYSTEM_CMDS and role != 'ADMIN':
                bot.reply_to(message, "🛡️ Comando reservado para Administrador.")
                return

            # --- COMMAND DISPATCH ---
            if cmd_part == '/id':
                bot.reply_to(message, f"🆔 Tu ID: `{user_id}`\nRol: *{role}*", parse_mode='Markdown')           
            # General / Hybrid
            elif cmd_part == '/start':
                handle_start(message)
            elif cmd_part == '/help':
                send_welcome(message)
            elif cmd_part == '/risk':
                handle_risk(message)
            elif cmd_part == '/strategy':
                handle_strategy(message)
            elif cmd_part == '/status':
                handle_status(message)
            
            # System (System Only - Filtered above)
            elif cmd_part in ['/toggle_group', '/togglegroup', '/toggle']:
                handle_toggle_group(message)
            elif cmd_part in ['/set_interval', '/setinterval', '/set_cooldown']:
                handle_set_interval(message)
            elif cmd_part == '/debug':
                handle_debug(message)
            
            # User Config & Trading (Allowed for Subscribers)
            elif cmd_part in ['/config', '/status']: # Alias /config to /status
                handle_status(message)
            elif cmd_part == '/price':
                handle_price(message)
            elif cmd_part in ['/set_keys', '/setkeys']:
                handle_set_keys(message)
            elif cmd_part in ['/set_leverage', '/setleverage']:
                handle_set_leverage(message)
            elif cmd_part in ['/set_margin', '/setmargin']:
                handle_set_margin(message)
            elif cmd_part in ['/set_spot_alloc', '/setspotallocation', '/set_spot_allocation']:
                handle_set_spot_allocation(message)
            elif cmd_part == '/wallet':
                handle_wallet(message)
            
            # Manual Spot
            elif cmd_part == '/buy':
                handle_manual_buy_spot(message)
            
            # --- AUTOMATION FLOW ---
            elif cmd_part == '/watcher':
                handle_mode_switch(message, 'WATCHER')
            elif cmd_part == '/copilot':
                handle_mode_switch(message, 'COPILOT')
            elif cmd_part == '/pilot':
                handle_mode_switch(message, 'PILOT')
            elif cmd_part == '/mode':
                handle_get_mode(message)
            
            # Manual Trading
            elif cmd_part == '/long':
                handle_manual_long(message)
            elif cmd_part == '/short':
                handle_manual_short(message)
            elif cmd_part == '/sell':
                handle_manual_sell(message)
            elif cmd_part == '/close':
                handle_manual_close(message)
            elif cmd_part == '/closeall':
                handle_manual_closeall(message)
            elif cmd_part in ['/reset_pilot', '/resetpilot']:
                 handle_reset_pilot(message)
            elif cmd_part in ['/personality', '/pers']:
                handle_personality(message)
            else:
               bot.reply_to(message, f"🤷‍♂️ Comando desconocido: {cmd_part}")

    except Exception as e:
        print(f"❌ Error en dispatcher: {e}")
# --- TRADING LOOP ---

def run_trading_loop():
    """Bucle de Trading en Background"""
    print("🚀 Bucle de Trading Híbrido Iniciado (Background)...")
    
    # State Tracking (Smart Filtering)
    last_alert_times = {}
    last_alert_prices = {}
    last_signals = {} # Tracks 'BUY', 'SELL' etc per asset

    while True:
        # QUANTUM BYPASS
        if USE_QUANTUM_ENGINE:
            # Legacy loop sleeps to allow QuantumBridge to handle signals
            time.sleep(30)
            continue
            
        try:
            # Iterar Grupos Activos
            for group_name, assets in ASSET_GROUPS.items():
                if not GROUP_CONFIG.get(group_name, False):
                    continue
                    
                for asset in assets:
                    try:
                        current_time = time.time()
                        
                        # 1. PROCESS FIRST (Always Monitor)
                        success, res = process_asset(asset)
                        if not success: continue
                        
                        m = res['metrics']
                        curr_price = m['close']
                        
                        # Determine Current Signal Type (Unified)
                        curr_sig_type = None
                        if res['signal_spot']: curr_sig_type = 'SPOT_BUY'
                        elif res['signal_futures'] in ['BUY', 'SHORT', 'CLOSE_LONG', 'CLOSE_SHORT', 'EXIT_ALL']: 
                            curr_sig_type = res['signal_futures']
                        
                        # --- SMART FILTER ---
                        last_time = last_alert_times.get(asset, 0)
                        last_price = last_alert_prices.get(asset, 0)
                        last_sig = last_signals.get(asset, None)
                        
                        # Conditions
                        time_passed = (current_time - last_time) > SIGNAL_COOLDOWN
                        price_change = abs((curr_price - last_price) / last_price) if last_price > 0 else 0
                        is_big_move = price_change > 0.008 # 0.8% deviation
                        is_new_signal = (curr_sig_type is not None) and (curr_sig_type != last_sig)
                        
                        # Has the bot signaled anything?
                        has_signal = res['signal_spot'] or (res['signal_futures'] not in ['WAIT'])
                        
                        # Strict Filter: Pass if (Time OK OR Big Move OR New Signal) AND Has Signal
                        should_alert = has_signal and (time_passed or is_big_move or is_new_signal)
                        
                        # If filtering active, skip
                        if not should_alert:
                            continue
                            
                        # UPDATE STATE (Only if Alerting)
                        last_alert_times[asset] = current_time
                        last_alert_prices[asset] = curr_price
                        if curr_sig_type: last_signals[asset] = curr_sig_type
                        

                        
                        # 2. Alertas
                        
                        # SPOT LOGIC
                        if res['signal_spot']:
                            
                            # Prepare basic alert text
                            base_msg = (
                                f"💎 *SEÑAL SPOT: {asset}*\n"
                                f"Estrategia: Reversión a la Media\n"
                                f"Precio: ${m['close']:,.2f}\n"
                                f"Razón: {res['reason_spot']}"
                            )
                            
                            # Iterate Sessions
                            all_sessions = session_manager.get_all_sessions()
                            for session in all_sessions:
                                mode = session.config.get('mode', 'WATCHER')
                                cid = session.chat_id
                                
                                if mode == 'PILOT':
                                    # AUTO BUY
                                    success_t, info = session.execute_spot_buy(asset)
                                    status_icon = "✅" if success_t else "❌"
                                    
                                    # Identify Group
                                    group_name = "UNKNOWN"
                                    for g_key, g_assets in ASSET_GROUPS.items():
                                        if asset in g_assets:
                                            group_name = g_key
                                            break

                                    bot.send_message(cid, f"{base_msg}\n\n🤖 *PILOT ACTION ON {group_name}:*\n{status_icon} {info}", parse_mode='Markdown')
                                    
                                elif mode == 'COPILOT':
                                    # PROPOSE
                                    markup = types.InlineKeyboardMarkup()
                                    # Data: BUY|SYMBOL|SPOT_LONG
                                    btn_yes = types.InlineKeyboardButton("✅ Comprar (20%)", callback_data=f"BUY|{asset}|SPOT")
                                    btn_no = types.InlineKeyboardButton("❌ Rechazar", callback_data=f"IGNORE|{asset}|SPOT")
                                    markup.add(btn_yes, btn_no)
                                    bot.send_message(cid, f"{base_msg}\n\n🤝 *PROPUESTA COPILOT:*", reply_markup=markup, parse_mode='Markdown')
                                    
                                else:
                                    # WATCHER
                                    bot.send_message(cid, base_msg, parse_mode='Markdown')

                            continue # Stop here for Spot signals
                            
                        # FUTUROS ALERTS (Con State)
                        curr_state = pos_state.get(asset, 'NEUTRAL')
                        fut_sig = res['signal_futures']
                        
                        # --- DISPATCH SIGNAL TO SESSIONS ---
                        # We iterate all sessions to respect their individual modes
                        all_sessions = session_manager.get_all_sessions()
                        
                        # Also include Non-Session Chat IDs (Env Var) as WATCHERS
                        env_chats = set(TELEGRAM_CHAT_IDS)
                        session_chats = set(s.chat_id for s in all_sessions)
                        
                        # 1. PROCESS SESSIONS (Watcher/Copilot/Pilot)
                        
                        # Determine Action based on Signal + State
                        action_needed = None
                        target_side = None
                        
                        if fut_sig == 'BUY' and curr_state == 'NEUTRAL':
                            action_needed = 'OPEN_LONG'
                            pos_state[asset] = 'LONG'
                            
                        elif fut_sig == 'SHORT' and curr_state == 'NEUTRAL':
                            action_needed = 'OPEN_SHORT'
                            pos_state[asset] = 'SHORT'
                            
                        elif fut_sig == 'CLOSE_LONG' and curr_state == 'LONG':
                            action_needed = 'CLOSE'
                            target_side = 'LONG'
                            pos_state[asset] = 'NEUTRAL'

                        elif fut_sig == 'CLOSE_SHORT' and curr_state == 'SHORT':
                            action_needed = 'CLOSE'
                            target_side = 'SHORT'
                            pos_state[asset] = 'NEUTRAL'
                            
                        elif fut_sig == 'EXIT_ALL' and curr_state != 'NEUTRAL':
                            action_needed = 'CLOSE'
                            target_side = curr_state # Close whatever is open
                            pos_state[asset] = 'NEUTRAL'
                        
                        if not action_needed:
                            continue # Nothing to do

                        # Prepare Message (Dynamic Per Session)
                        # We cannot prepare a single text because each session might have a different personality.
                        # We defer message generation to the dispatch loop.

                        # Dispatch
                        for session in all_sessions:
                            mode = session.mode
                            cid = session.chat_id
                            p_key = session.config.get('personality', 'NEXUS')
                            
                            # GENERATE MESSAGE FOR THIS SESSION
                            msg_text = ""
                            if action_needed == 'OPEN_LONG':
                                msg_text = personality_manager.get_message(
                                    p_key, 'TRADE_LONG', 
                                    asset=asset, price=m['close'], reason=res['reason_futures']
                                )
                            elif action_needed == 'OPEN_SHORT':
                                msg_text = personality_manager.get_message(
                                    p_key, 'TRADE_SHORT', 
                                    asset=asset, price=m['close'], reason=res['reason_futures']
                                )
                            elif action_needed == 'CLOSE':
                                msg_text = personality_manager.get_message(
                                    p_key, 'TRADE_CLOSE', 
                                    asset=asset, side=target_side, reason=res['reason_futures']
                                )

                            try:
                                if mode == 'PILOT':
                                    # AUTO EXECUTE
                                    if action_needed == 'OPEN_LONG':
                                        ok, res_msg = session.execute_long_position(asset, atr=m['atr'])
                                    elif action_needed == 'OPEN_SHORT':
                                        ok, res_msg = session.execute_short_position(asset, atr=m['atr'])
                                    else: # CLOSE
                                        ok, res_msg = session.execute_close_position(asset)
                                        # PHANTOM CLOSE CHECK
                                        if not ok and "No open position" in res_msg:
                                            # Silent correct
                                            pos_state[asset] = 'NEUTRAL'
                                            continue 
                                        
                                    # Dynamic Pilot Action Msg
                                    final_msg = personality_manager.get_message(p_key, 'PILOT_ACTION', msg=res_msg)
                                    bot.send_message(cid, final_msg, parse_mode='Markdown')
                                        
                                elif mode == 'COPILOT':
                                    # INTERACTIVE BUTTONS
                                    markup = InlineKeyboardMarkup()
                                    if action_needed == 'OPEN_LONG':
                                        markup.add(
                                            InlineKeyboardButton("✅ Entrar LONG", callback_data=f"BUY|{asset}|LONG"),
                                            InlineKeyboardButton("❌ Ignorar", callback_data=f"IGNORE|{asset}|LONG")
                                        )
                                    elif action_needed == 'OPEN_SHORT':
                                        markup.add(
                                            InlineKeyboardButton("✅ Entrar SHORT", callback_data=f"BUY|{asset}|SHORT"),
                                            InlineKeyboardButton("❌ Ignorar", callback_data=f"IGNORE|{asset}|SHORT")
                                        )
                                    else: # CLOSE
                                        markup.add(
                                            InlineKeyboardButton("✅ Cerrar Ahora", callback_data=f"CLOSE|{asset}|ANY"),
                                            InlineKeyboardButton("❌ Mantener", callback_data=f"IGNORE|{asset}|ANY")
                                        )
                                    bot.send_message(cid, msg_text, reply_markup=markup, parse_mode='Markdown')
                                    
                                else: # WATCHER (Default)
                                    bot.send_message(cid, msg_text, parse_mode='Markdown')
                                    
                            except Exception as e:
                                print(f"Error dispatching to {cid}: {e}")

                        # 3. PROCESS CIRCUIT BREAKER (Safety)
                        triggered, msg = session.check_circuit_breaker()
                        if triggered:
                             # Dynamic Message
                             p_key = session.config.get('personality', 'NEXUS')
                             cb_msg = personality_manager.get_message(p_key, 'CB_TRIGGER')
                             bot.send_message(cid, cb_msg, parse_mode='Markdown')

                    except Exception as e:
                        print(f"⚠️ Error procesando {asset}: {e}")
            
            # --- END OF ASSET LOOP ---
            
            # (Redundant CB check removed - it's handled above per iteration/signal, 
            #  but technically CB check should be frequent. keeping loop clean for now)

        except Exception as e:
            print(f"❌ Error CRÍTICO en bucle de trading: {e}")
            
        time.sleep(60)

# --- QUANTUM BRIDGE INTEGRATION ---
from antigravity_quantum.bridge import QuantumBridge
quantum_bridge = None
USE_QUANTUM_ENGINE = True # Auto-enable on next restart

def dispatch_quantum_signal(signal):
    """
    Callback triggered by QuantumBridge from Background Thread.
    Routes signals to all active sessions.
    """
    try:
        asset = signal.symbol
        action = signal.action # BUY, SELL
        price = signal.price
        conf = signal.confidence
        reason = f"{signal.metadata} (Conf: {conf:.2f})"
        
        # Log to Console
        print(f"⚡ QUANTUM DISPATCH: {action} on {asset}")
        
        # Map Quantum Action to Bot Action
        action_needed = None
        target_side = None
        
        if action == "BUY":
            action_needed = 'OPEN_LONG'
        elif action == "SELL":
            action_needed = 'CLOSE'
            target_side = 'LONG' 
        
        if not action_needed: return

        # Iterate Sessions
        all_sessions = session_manager.get_all_sessions()
        
        for session in all_sessions:
            mode = session.config.get('mode', 'WATCHER')
            cid = session.chat_id
            p_key = session.config.get('personality', 'NEXUS')
            
            # Prepare Message
            msg_text = ""
            if action_needed == 'OPEN_LONG':
                msg_text = personality_manager.get_message(
                    p_key, 'TRADE_LONG', 
                    asset=asset, price=price, reason=reason
                )
            elif action_needed == 'CLOSE':
                msg_text = personality_manager.get_message(
                    p_key, 'TRADE_CLOSE', 
                    asset=asset, side=target_side, reason=reason
                )

            # Mode Logic
            try:
                if mode == 'PILOT':
                    # AUTO EXECUTE
                    if action_needed == 'OPEN_LONG':
                        ok, res_msg = session.execute_long_position(asset, atr=0) 
                    elif action_needed == 'CLOSE':
                        ok, res_msg = session.execute_close_position(asset)
                    else:
                        ok, res_msg = False, "Unknown Action"
                        
                    if ok:
                        final_msg = personality_manager.get_message(p_key, 'PILOT_ACTION', msg=res_msg)
                        bot.send_message(cid, final_msg, parse_mode='Markdown')
                        
                elif mode == 'COPILOT':
                    markup = InlineKeyboardMarkup()
                    if action_needed == 'OPEN_LONG':
                        markup.add(
                            InlineKeyboardButton("✅ Entrar (Quantum)", callback_data=f"BUY|{asset}|LONG"),
                            InlineKeyboardButton("❌ Ignorar", callback_data=f"IGNORE|{asset}|LONG")
                        )
                    elif action_needed == 'CLOSE':
                        markup.add(
                            InlineKeyboardButton("✅ Cerrar (Quantum)", callback_data=f"CLOSE|{asset}|ANY"),
                            InlineKeyboardButton("❌ Mantener", callback_data=f"IGNORE|{asset}|ANY")
                        )
                    bot.send_message(cid, msg_text, reply_markup=markup, parse_mode='Markdown')
                    
                else: # WATCHER
                     bot.send_message(cid, msg_text, parse_mode='Markdown')
                     
            except Exception as e:
                print(f"⚠️ Dispatch Error {cid}: {e}")

    except Exception as e:
        print(f"❌ Quantum Dispatch Critical: {e}")

# --- RESTORED HANDLERS ---

@bot.message_handler(commands=['help'])
def send_welcome(message):
    help_text = (
        "🤖 *ANTIGRAVITY BOT v3.3 - QUANTUM*\n"
        "〰️〰️〰️〰️〰️〰️\n\n"
        "ℹ️ *INFO & MERCADO*\n"
        "• /price - Panel de Precios y Señales.\n"
        "• /about - Sobre el sistema.\n"
        "• /strategy - Lógica de trading.\n"
        "• /risk - Gestión de riesgo.\n\n"
        
        "⚙️ *SISTEMA*\n"
        "• /status - Estado y Configuración.\n"
        "• /strategies - Motores y Estrategias.\n"
        "• /config - Panel de Ajustes.\n\n"
        
        "🎮 *MODOS OPERATIVOS*\n"
        "• /pilot - Auto.\n"
        "• /copilot - Asistido.\n"
        "• /watcher - Manual.\n\n"
        
        "🔧 *OTROS*\n"
        "• /personality - Cambiar la personalidad.\n"
        "• /togglegroup <GRUPO> - Filtros."
    )
    try:
        bot.reply_to(message, help_text, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, help_text.replace('*', '').replace('`', ''))

@threaded_handler
@bot.message_handler(commands=['start'])
def handle_start(message):
    """ Bienvenida Profesional con Efecto de Carga """
    # 1. Mensaje de carga inicial
    msg_load = bot.reply_to(message, "🔄 _Despertando funciones cognitivas..._", parse_mode='Markdown')
    
    # Simular micro-check
    time.sleep(0.5)
    
    # 2. Verificar estado
    me = bot.get_me()
    status_icon = "🟢" if me else "🔴"
    status_text = "SISTEMA ONLINE" if me else "ERROR DE CONEXIÓN"
    
    chat_id = str(message.chat.id)
    session = session_manager.get_session(chat_id)
    
    # 3. Datos de Sesión
    mode = "WATCHER"
    auth = "🔒 Sin Credenciales"
    
    if session:
        cfg = session.get_configuration()
        mode = cfg.get('mode', 'WATCHER')
        
        # Build Auth String
        auth_list = []
        if session.client:
            auth_list.append("Binance")
        if session.alpaca_client:
            auth_list.append("🦙 Alpaca")
            
        if auth_list:
            auth = "🔑 " + " + ".join(auth_list)
    
    # Get Personality
    p_key = session.config.get('personality', 'STANDARD_ES') if session else 'STANDARD_ES'

    # 4. Mensaje Final Dinámico (Updated for Button UI)
    welcome = personality_manager.get_message(
        p_key, 'WELCOME',
        status_text=status_text,
        status_icon=status_icon,
        mode=mode,
        auth=auth
    )
    
    # Interactive Menu (Buttons)
    markup = InlineKeyboardMarkup(row_width=2)
    # Row 1: Status | Wallet
    markup.add(
        InlineKeyboardButton("📊 Estado", callback_data="CMD|/status"),
        InlineKeyboardButton("💰 Cartera", callback_data="CMD|/wallet")
    )
    # Row 2: Modes
    markup.add(
        InlineKeyboardButton("🦅 Pilot", callback_data="CMD|/pilot"),
        InlineKeyboardButton("🤝 Copilot", callback_data="CMD|/copilot"),
        InlineKeyboardButton("👀 Watcher", callback_data="CMD|/watcher")
    )
    # Row 3: Config / Personality
    markup.add(
        InlineKeyboardButton("🧠 Persona", callback_data="CMD|/personality"),
        InlineKeyboardButton("⚙️ Config", callback_data="CMD|/config")
    )
    # Row 4: Info (About / Strategy)
    markup.add(
        InlineKeyboardButton("ℹ️ Sobre el Bot", callback_data="CMD|/about"),
        InlineKeyboardButton("🧠 Info Strategy", callback_data="CMD|/strategy")
    )
    # Row 5: Price & Strategies
    markup.add(
        InlineKeyboardButton("📈 Precios", callback_data="CMD|/price"),
        InlineKeyboardButton("🎛️ Motores", callback_data="CMD|/strategies")
    )
    
    # Row 6: Help
    markup.add(InlineKeyboardButton("❓ Ayuda", callback_data="CMD|/help"))

    bot.edit_message_text(welcome, chat_id=chat_id, message_id=msg_load.message_id, parse_mode='Markdown', reply_markup=markup)

# --- CALLBACK QUERY HANDLER ---
# Remove @threaded_handler to ensure synchronous dispatch and proper error catching.
# The dispatched functions handle their own threading if needed.
@bot.callback_query_handler(func=lambda call: True)
def handle_query(call):
    # 1. DEBUG LOGGING
    print(f"DEBUG: Callback received: {call.data} from {call.message.chat.id}")
    
    try:
        chat_id = str(call.message.chat.id)
        session = session_manager.get_session(chat_id)
        
        data = call.data
        parts = data.split('|')
        cmd = parts[0]

        # --- MENU COMMANDS ---
        if cmd == 'CMD':
            sub_cmd = parts[1]
            try:
                bot.answer_callback_query(call.id) # Ack immediately
            except: pass

            # Dispatch
            if sub_cmd == '/status': handle_status(call.message)
            elif sub_cmd == '/wallet': handle_wallet(call.message)
            elif sub_cmd == '/pilot': handle_mode_switch(call.message, 'PILOT')
            elif sub_cmd == '/copilot': handle_mode_switch(call.message, 'COPILOT')
            elif sub_cmd == '/watcher': handle_mode_switch(call.message, 'WATCHER')
            elif sub_cmd == '/personality': handle_personality(call.message)
            elif sub_cmd == '/config': handle_config(call.message)
            elif sub_cmd == '/help': send_welcome(call.message)
            elif sub_cmd == '/about': handle_about(call.message)
            elif sub_cmd == '/strategy': handle_strategy(call.message)
            elif sub_cmd == '/price': handle_price(call.message)
            elif sub_cmd == '/strategies': handle_strategies(call.message)
            elif sub_cmd == '/contracts': handle_strategies(call.message)
            elif sub_cmd == '/togglegroup': handle_toggle_group(call.message)
            elif sub_cmd == '/assets': handle_assets(call.message)
            return
        
        # --- REQUIRES SESSION (Write Actions) ---
        if not session:
            try:
                bot.answer_callback_query(call.id, "⚠️ Sin sesión activa.")
                bot.send_message(chat_id, "⚠️ No tienes sesión activa. Usa /set_keys para configurar.", parse_mode='Markdown')
            except: pass
            return

        # --- STRATEGY TOGGLES ---
        if cmd == "TOGGLE":
            try:
                strat = parts[1] # SCALPING or GRID
                current = ENABLED_STRATEGIES.get(strat, False)
                ENABLED_STRATEGIES[strat] = not current # Flip
                state_manager.save_state(ENABLED_STRATEGIES, GROUP_CONFIG, DISABLED_ASSETS, session) # SAVE
                
                # Refresh Menu
                new_state = "✅ ACTIVADO" if ENABLED_STRATEGIES[strat] else "❌ DESACTIVADO"
                bot.answer_callback_query(call.id, f"{strat} ahora: {new_state}")
                
                # Re-render menu
                markup = InlineKeyboardMarkup()
                s_state = "✅ ACTIVADO" if ENABLED_STRATEGIES['SCALPING'] else "❌ DESACTIVADO"
                g_state = "✅ ACTIVADO" if ENABLED_STRATEGIES['GRID'] else "❌ DESACTIVADO"
                m_state = "✅ ACTIVADO" if ENABLED_STRATEGIES.get('MEAN_REVERSION', True) else "❌ DESACTIVADO"
                
                markup.add(InlineKeyboardButton(f"⚡ Scalping: {s_state}", callback_data="TOGGLE|SCALPING"))
                markup.add(InlineKeyboardButton(f"🕸️ Grid: {g_state}", callback_data="TOGGLE|GRID"))
                markup.add(InlineKeyboardButton(f"📉 Mean Rev: {m_state}", callback_data="TOGGLE|MEAN_REVERSION"))
                
                bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=markup)
            except Exception as e:
                print(f"Error in TOGGLE: {e}")
                bot.answer_callback_query(call.id, "❌ Error al cambiar.")
            return

        # --- GROUP TOGGLES ---
        if cmd == "TOGGLEGRP":
            try:
                group = parts[1]
                if group in GROUP_CONFIG:
                    GROUP_CONFIG[group] = not GROUP_CONFIG[group]
                    state_manager.save_state(ENABLED_STRATEGIES, GROUP_CONFIG, DISABLED_ASSETS, session) # SAVE
                    bot.answer_callback_query(call.id, f"{group}: {'✅' if GROUP_CONFIG[group] else '❌'}")
                    
                    # Re-render
                    markup = InlineKeyboardMarkup()
                    for g, enabled in GROUP_CONFIG.items():
                        state = "✅" if enabled else "❌"
                        markup.add(InlineKeyboardButton(f"{state} {g}", callback_data=f"TOGGLEGRP|{g}"))
                    bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=markup)
            except Exception as e:
                 print(f"Error in TOGGLEGRP: {e}")
                 bot.answer_callback_query(call.id, "❌ Error al cambiar grupo.")
            return

        if cmd == "TOGGLEASSET":
            try:
                asset = parts[1]
                if asset in DISABLED_ASSETS:
                    DISABLED_ASSETS.remove(asset)
                    bot.answer_callback_query(call.id, f"✅ {asset} ACTIVADO")
                else:
                    DISABLED_ASSETS.add(asset)
                    bot.answer_callback_query(call.id, f"❌ {asset} BLOQUEADO")
                
                state_manager.save_state(ENABLED_STRATEGIES, GROUP_CONFIG, DISABLED_ASSETS, session) # SAVE
                
                # Re-render (Limit 50 hack)
                markup = InlineKeyboardMarkup(row_width=3)
                buttons = []
                active_assets = []
                for g, enabled in GROUP_CONFIG.items():
                    if enabled: active_assets.extend(ASSET_GROUPS.get(g, []))
                    
                for a in active_assets[:50]:
                    is_disabled = a in DISABLED_ASSETS
                    icon = "❌" if is_disabled else "✅"
                    buttons.append(InlineKeyboardButton(f"{icon} {a}", callback_data=f"TOGGLEASSET|{a}"))
                markup.add(*buttons)
                bot.edit_message_reply_markup(chat_id, call.message.message_id, reply_markup=markup)
            except Exception as e:
                print(f"Error in TOGGLEASSET: {e}")
                bot.answer_callback_query(call.id, "❌ Error.")
            return

        # --- TRADING COMMANDS ---
        if cmd == "BUY":
            asset = parts[1]
            side = parts[2]
            
            try:
                bot.answer_callback_query(call.id, f"🚀 Ejecutando {side} en {asset}...")
                
                ok = False
                msg = "Error desconocido"

                if side == "LONG":
                    ok, msg = session.execute_long_position(asset, atr=0) 
                elif side == "SHORT":
                    ok, msg = session.execute_short_position(asset, atr=0)
                elif side == "SPOT":
                     ok, msg = session.execute_spot_buy(asset)
                else:
                     msg = f"Tipo de orden desconocido: {side}"
                    
                bot.send_message(chat_id, f"RESULTADO: {msg}", parse_mode='Markdown')
            except Exception as e:
                 bot.send_message(chat_id, f"❌ Error ejecutando orden: {e}")

        elif cmd == "CLOSE":
            asset = parts[1]
            try:
                bot.answer_callback_query(call.id, f"📉 Cerrando {asset}...")
                ok, msg = session.execute_close_position(asset)
                bot.send_message(chat_id, f"RESULTADO: {msg}", parse_mode='Markdown')
            except Exception as e:
                 bot.send_message(chat_id, f"❌ Error cerrando: {e}")
            
        elif cmd == "IGNORE":
            try:
                bot.answer_callback_query(call.id, "❌ Señal descartada.")
                bot.delete_message(chat_id, call.message.message_id)
            except: pass

        elif cmd == "CFG":
            # Personality Config
            sub = parts[1] # PERS, LEV_MENU, MARGIN_MENU, LEV, MARGIN
            val = parts[2] if len(parts) > 2 else None
            
            try:
                if sub == "PERS":
                    session.config['personality'] = val
                    state_manager.save_state(ENABLED_STRATEGIES, GROUP_CONFIG, DISABLED_ASSETS, session)
                    
                    name = personality_manager.PROFILES.get(val, {}).get('NAME', val)
                    bot.answer_callback_query(call.id, f"🧠 Personalidad: {name}")
                    bot.send_message(chat_id, f"🧠 **Personalidad Cambiada a:** {name}", parse_mode='Markdown')
                    # AUTO START
                    time.sleep(0.5)
                    handle_start(call.message)
                    
                elif sub == "LEV_MENU":
                    handle_set_leverage(call.message)
                    bot.answer_callback_query(call.id)
                    
                elif sub == "MARGIN_MENU":
                    handle_set_margin(call.message)
                    bot.answer_callback_query(call.id)
                    
                elif sub == "LEV": # CFG|LEV|10
                    session.config['leverage'] = int(val)
                    state_manager.save_state(ENABLED_STRATEGIES, GROUP_CONFIG, DISABLED_ASSETS, session)
                    bot.answer_callback_query(call.id, f"⚖️ Lev: {val}x")
                    bot.send_message(chat_id, f"⚖️ **Apalancamiento actualizado:** {val}x", parse_mode='Markdown')
                    
                elif sub == "MARGIN": # CFG|MARGIN|0.1
                    session.config['max_capital_pct'] = float(val)
                    state_manager.save_state(ENABLED_STRATEGIES, GROUP_CONFIG, DISABLED_ASSETS, session)
                    bot.answer_callback_query(call.id, f"💰 Margin: {float(val)*100:.0f}%")
                    bot.send_message(chat_id, f"💰 **Margen actualizado:** {float(val)*100:.0f}%", parse_mode='Markdown')
                
                elif sub == "SPOT": # CFG|SPOT|0.10
                     session.config['spot_allocation_pct'] = float(val)
                     state_manager.save_state(ENABLED_STRATEGIES, GROUP_CONFIG, DISABLED_ASSETS, session)
                     bot.answer_callback_query(call.id, f"💎 Spot Alloc: {float(val)*100:.0f}%")
                     bot.send_message(chat_id, f"💎 **Asignación Spot Actualizada:** {float(val)*100:.0f}% de USDT Libre", parse_mode='Markdown')

            except Exception as e:
                print(f"Error in CFG: {e}")
                bot.answer_callback_query(call.id, "❌ Error de config.")

    except Exception as e:
        print(f"❌ Error CRÍTICO en handle_query: {e}")
        try:
            bot.answer_callback_query(call.id, "❌ Error Interno")
        except: pass

@bot.message_handler(commands=['togglegroup', 'toggle'])
def handle_toggle_group(message):
    """
    Selector Interactivo de Grupos
    Uso: /toggle (Menu) o /toggle <GRUPO> (Directo)
    """
    try:
        args = message.text.split()
        chat_id = str(message.chat.id)
        session = session_manager.get_session(chat_id)

        # 1. DIRECT TOGGLE (Text Argument)
        if len(args) > 1:
            # Normalize user input
            target_group = args[1].upper()
            
            # Map aliases if needed (e.g. STOCKS -> STOCK)
            # For now, simplistic matching against GROUP_CONFIG keys
            matched_key = None
            for key in GROUP_CONFIG.keys():
                if key.upper() == target_group:
                    matched_key = key
                    break
            
            if matched_key:
                # Toggle
                current_val = GROUP_CONFIG[matched_key]
                GROUP_CONFIG[matched_key] = not current_val
                
                # Save
                state_manager.save_state(ENABLED_STRATEGIES, GROUP_CONFIG, DISABLED_ASSETS, session)
                
                new_status = "✅ ACTIVADO" if GROUP_CONFIG[matched_key] else "❌ DESACTIVADO"
                bot.reply_to(message, f"⚙️ *GRUPO {matched_key}:* {new_status}", parse_mode='Markdown')
            else:
                bot.reply_to(message, f"⚠️ Grupo '{target_group}' no encontrado.\nGrupos: {', '.join(GROUP_CONFIG.keys())}")
            return

        # 2. INTERACTIVE MENU (No Args)
        markup = InlineKeyboardMarkup()
        for group, enabled in GROUP_CONFIG.items():
            state = "✅" if enabled else "❌"
            markup.add(InlineKeyboardButton(f"{state} {group}", callback_data=f"TOGGLEGRP|{group}"))
            
        bot.reply_to(message, "📡 **CONFIGURACIÓN DE RADARES**\nActiva/Desactiva grupos de mercado:\n(O usa `/toggle <NOMBRE>` para hacerlo rápido)", reply_markup=markup, parse_mode='Markdown')

    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")

# --- PERSONALITY COMMAND ---
@threaded_handler
@bot.message_handler(commands=['personality', 'pers'])
def handle_personality(message):
    cid = message.chat.id
    markup = InlineKeyboardMarkup(row_width=2)
    buttons = []
    
    for key, profile in personality_manager.PROFILES.items():
        name = profile['NAME']
        btn = InlineKeyboardButton(name, callback_data=f"CFG|PERS|{key}")
        buttons.append(btn)
        
    markup.add(*buttons)
    bot.reply_to(message, "🧠 **SELECCIONA PERSONALIDAD**\n¿Quién quieres que opere por ti hoy?", reply_markup=markup, parse_mode='Markdown')

# --- STRATEGY TOGGLE COMMAND ---
from antigravity_quantum.config import ENABLED_STRATEGIES

@bot.message_handler(commands=['strategies', 'contracts'])
def handle_strategies(message):
    cid = message.chat.id
    
    markup = InlineKeyboardMarkup()
    
    # 1. SCALPING TOGGLE
    scalp_state = "✅ ACTIVADO" if ENABLED_STRATEGIES['SCALPING'] else "❌ DESACTIVADO"
    markup.add(InlineKeyboardButton(f"⚡ Scalping: {scalp_state}", callback_data="TOGGLE|SCALPING"))
    
    # 2. GRID TOGGLE
    grid_state = "✅ ACTIVADO" if ENABLED_STRATEGIES['GRID'] else "❌ DESACTIVADO"
    markup.add(InlineKeyboardButton(f"🕸️ Grid: {grid_state}", callback_data="TOGGLE|GRID"))
    
    # 3. MEAN REVERSION TOGGLE
    mean_state = "✅ ACTIVADO" if ENABLED_STRATEGIES.get('MEAN_REVERSION', True) else "❌ DESACTIVADO"
    markup.add(InlineKeyboardButton(f"📉 Mean Rev: {mean_state}", callback_data="TOGGLE|MEAN_REVERSION"))
    
    info_text = (
        "⚙️ **CONFIGURACIÓN DE ESTRATEGIAS (QUANTUM)**\n\n"
        "Controla qué motores están activos en el análisis de mercado:\n\n"
        "⚡ **Scalping (High Vol)**: Opera rupturas en ZEC, SOL, SUI. (Alto Riesgo)\n"
        "🕸️ **Grid (Accumulation)**: Opera rangos en ADA, ZEC. (Medio Riesgo)\n"
        "📉 **Mean Reversion**: Activo por defecto en el resto. (Bajo Riesgo)"
    )
    
    bot.send_message(cid, info_text, reply_markup=markup, parse_mode='Markdown')

def start_bot():
    global session_manager, quantum_bridge
    
    # --- LOAD PERSISTENT STATE ---
    saved_state = state_manager.load_state()
    
    # 1. Update Strategies
    if "enabled_strategies" in saved_state:
        ENABLED_STRATEGIES.update(saved_state["enabled_strategies"])
        
    # 2. Update Groups
    if "group_config" in saved_state:
        GROUP_CONFIG.update(saved_state["group_config"])
        
    # 3. Update Disabled Assets
    # 3. Update Disabled Assets
    if "disabled_assets" in saved_state:
        # Clear and update set
        DISABLED_ASSETS.clear()
        for asset in saved_state["disabled_assets"]:
            DISABLED_ASSETS.add(asset)
            
    print("💾 Persistent State Applied.")

    session_manager = SessionManager()
    
    # 4. Apply Session Config (Pers, Lev, Margin)
    # Note: SessionManager defaults new sessions. We need to inject saved config into the default 'session' if created.
    # For now, we update the manager's default template or apply when session is created.
    # A simple way for single-user bot:
    if "session_config" in saved_state:
        pass # Session logic handled inside SessionManager or we apply it to the first session detected.

    # Start Quantum Bridge if Enabled
    if USE_QUANTUM_ENGINE:
        print("🌌 Initializing Quantum Bridge...")
        quantum_bridge = QuantumBridge(notification_callback=dispatch_quantum_signal)
        quantum_bridge.start()
    
    # Iniciar Trading Thread
    t_trading = threading.Thread(target=run_trading_loop)
    t_trading.daemon = True
    t_trading.start()
    
    # Iniciar Polling
    if bot:
        print("📡 Iniciando Telegram Polling (Main Thread)...")
        try:
            bot.delete_webhook(drop_pending_updates=True)
        except: pass

        while True:
            try:
                print("🔄 Starting Infinity Polling...")
                bot.infinity_polling(timeout=20, long_polling_timeout=20)
            
            except Exception as e:
                print(f"❌ Polling Error: {e}")
                time.sleep(5)
    else:
        print("❌ Bot no inicializado.")
        while True: time.sleep(10)

if __name__ == "__main__":
    start_bot()
