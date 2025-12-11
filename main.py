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

from strategies.engine import StrategyEngine
from utils.trading_manager import SessionManager

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
            bot.reply_to(message, f"✅ *LONG EJECUTADO*\n{msg}", parse_mode='Markdown')
        else:
            bot.reply_to(message, f"❌ Error: {msg}")

    except Exception as e:
        bot.reply_to(message, f"❌ Error crítico: {e}")

@threaded_handler
def handle_manual_sell(message):
    """ /sell <SYMBOL> (Smart Sell: Close Long OR Open Short) """
    chat_id = str(message.chat.id)
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
                bot.reply_to(message, f"✅ *SHORT EJECUTADO*\n{msg}", parse_mode='Markdown')
            else:
                bot.reply_to(message, f"❌ Error: {msg}")
                
    except Exception as e:
         bot.reply_to(message, f"❌ Error crítico: {e}")

@threaded_handler
def handle_manual_close(message):
    """ /close <SYMBOL> """
    chat_id = str(message.chat.id)
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
        bot.reply_to(message, msg)
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")

@threaded_handler
def handle_manual_closeall(message):
    """ /closeall """
    chat_id = str(message.chat.id)
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
        
    if session.set_mode(mode):
        session_manager.save_sessions()
        descriptions = {
            'WATCHER': "👀 **WATCHER ACTIVADO**: Solo recibirás alertas de texto.",
            'COPILOT': "🤝 **COPILOT ACTIVADO**: Recibirás propuestas de operación para Aceptar/Rechazar.",
            'PILOT': "🤖 **PILOT ACTIVADO**: El bot operará automáticamente (Bajo tu riesgo)."
        }
        bot.reply_to(message, descriptions.get(mode, "Modo Actualizado."), parse_mode='Markdown')
    else:
        bot.reply_to(message, "❌ Error cambiando modo.")

def handle_get_mode(message):
    chat_id = str(message.chat.id)
    session = session_manager.get_session(chat_id)
    if not session: return
    
    mode = session.config.get('mode', 'WATCHER')
    bot.reply_to(message, f"🎮 Modo Actual: **{mode}**", parse_mode='Markdown')

# --- CALLBACK HANDLER (COPILOT) ---
@bot.callback_query_handler(func=lambda call: True)
@threaded_handler
def handle_trade_callback(call):
    print(f"🔘 Callback received: {call.data}")
    chat_id = str(call.message.chat.id)
    session = session_manager.get_session(chat_id)
    
    if not session:
        bot.answer_callback_query(call.id, "⚠️ Sesión no encontrada.")
        return

    try:
        # Data format: ACTION|SYMBOL|SIDE (e.g., BUY|BTCUSDT|LONG)
        data = call.data.split('|')
        action = data[0]
        
        if action == 'CFG':
            # Configuration Change
            key = data[1]
            val = data[2]
            
            if key == 'LEV':
                session.update_config('leverage', int(val))
                msg = f"⚖️ *Apalancamiento:* {val}x"
            elif key == 'MARGIN':
                session.update_config('max_capital_pct', float(val))
                msg = f"💰 *Margen Máx:* {float(val)*100:.0f}%"
            elif key == 'SPOT':
                session.update_config('spot_allocation_pct', float(val))
                msg = f"💎 *Asignación Spot:* {float(val)*100:.0f}%"
            
            session_manager.save_sessions()
            success = True
            bot.edit_message_text(f"✅ Configuración Actualizada:\n{msg}", chat_id=chat_id, message_id=call.message.message_id, parse_mode='Markdown')
            return # Exit after config update

        elif action == 'IGNORE':
            bot.edit_message_text(f"❌ Operación Rechazada par {data[1]}.", chat_id=chat_id, message_id=call.message.message_id)
            return

        symbol = data[1]
        side = data[2]
        
        bot.answer_callback_query(call.id, f"⏳ Ejecutando {action} {symbol}...")
        
        success = False
        msg = ""
        
        if action == 'BUY' and side == 'LONG':
            # Need ATR? Ideally passed in data, but limited space. Re-calc or pass 'None' (Fallback).
            success, msg = session.execute_long_position(symbol)
            
        elif action == 'BUY' and side == 'SHORT':
            success, msg = session.execute_short_position(symbol)

        elif action == 'BUY' and side == 'SPOT':
            success, msg = session.execute_spot_buy(symbol)
            
        elif action == 'CLOSE':
             success, msg = session.execute_close_position(symbol)
             
        # Update Message
        new_text = f"{call.message.text}\n\n{'✅' if success else '❌'} **RESULTADO:**\n{msg}"
        bot.edit_message_text(new_text, chat_id=chat_id, message_id=call.message.message_id, parse_mode='Markdown')
        
    except Exception as e:
        print(f"Callback Error: {e}")
        bot.answer_callback_query(call.id, "❌ Error procesando.")


# --- RESTORED HANDLERS ---

def send_welcome(message):
    help_text = (
        "🤖 *ANTIGRAVITY BOT v3.3 - QUANTUM*\n"
        "〰️〰️〰️〰️〰️〰️\n\n"
        "⚙️ *SISTEMA (ADMIN)*\n"
        "• /status - Ver estado, latencia y tendencias de mercado.\n"
        "• /risk - Consultar reglas de riesgos ('Smart Filters').\n"
        "• /debug - Diagnóstico técnico avanzado.\n"
        "• /config - Panel de configuración rápida.\n\n"
        
        "🎮 *MODOS OPERATIVOS*\n"
        "• /pilot - Modo Automático (Sin confirmación).\n"
        "• /copilot - Modo Asistido (Requiere aprobación).\n"
        "• /watcher - Modo Vigilancia (Solo alertas).\n\n"
        
        "🔫 *TRADING MANUAL*\n"
        "• /buy <TICKER> - Compra Spot instantánea.\n"
        "• /long <TICKER> - Abrir Long Futuros.\n"
        "• /short <TICKER> - Abrir Short Futuros.\n"
        "• /close <TICKER> - Cerrar posición.\n"
        "• /closeall - PÁNICO (Cierra todo).\n\n"
        
        "🔧 *AJUSTES*\n"
        "• /setleverage <x> - Apalancamiento (Ej: 10).\n"
        "• /setmargin <%> - Riesgo máx del capital (Ej: 0.1).\n"
        "• /togglegroup <GRUPO> - Activar/Desactivar Crypto/Stocks.\n"
        "• /resetpilot - Reiniciar contador de pérdidas (Circuit Breaker)."
    )
    try:
        bot.reply_to(message, help_text, parse_mode='Markdown')
    except Exception as e:
        bot.reply_to(message, help_text.replace('*', '').replace('`', ''))

def handle_risk(message):
    """Explication detallada de la gestión de riesgo activa"""
    chat_id = str(message.chat.id)
    session = session_manager.get_session(chat_id)
    
    # Defaults
    margin = "10%"
    sl_fixed = "2%"
    if session:
        margin = f"{session.config['max_capital_pct']*100:.1f}%"
        sl_fixed = f"{session.config['stop_loss_pct']*100:.1f}%"

    msg = (
        "🛡️ *MOTOR DE RIESGO E INTELIGENCIA (MTF)*\n"
        "〰️〰️〰️〰️〰️〰️\n"
        "1. *Filtro Multi-Timeframe (MTF)* 🧠\n"
        "   • El bot valida cada señal de 15m con la tendencia de **1 Hora**.\n"
        "   • ✅ **LONG** solo si 1H es Alcista (Precio > EMA200).\n"
        "   • ✅ **SHORT** solo si 1H es Bajista (Precio < EMA200).\n"
        "   • _Esto evita operar contra la marea institucional._\n\n"
        
        "2. *Gestión de Capital*\n"
        "   • **Posición Dinámica**: Riesgo fijo del **2%** por trade.\n"
        "   • **Stop Loss (ATR)**: Se adapta a la volatilidad real del activo.\n"
        "   • **Límite Global**: Nunca usará más del **{margin}** de tu cuenta total.\n\n"
        
        "3. *Salidas Inteligentes*\n"
        "   • **TP1 (50%)**: Asegura ganancia rápida (1.5R).\n"
        "   • **TP2 (Running)**: Deja correr ganancias con Trailing Stop.\n\n"
        
        "4. *Circuit Breaker (Seguridad Extrema)* 🚨\n"
        "   • Si detecta **5 pérdidas consecutivas** en modo PILOT, se degrada a **COPILOT** automáticamente.\n"
        "   • Use `/resetpilot` para reactivar tras una racha negativa."
    ).format(margin=margin)
    
    bot.reply_to(message, msg, parse_mode='Markdown')

def handle_start(message):
    """ Bienvenida Profesional con Efecto de Carga """
    # 1. Mensaje de carga inicial
    msg_load = bot.reply_to(message, "🔄 _Estableciendo enlace seguro con el Núcleo..._", parse_mode='Markdown')
    
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
        if session.client:
            auth = "🔑 Binance Vinculado"
    
    # 4. Mensaje Final
    welcome = (
        "🌌 *ANTIGRAVITY QUANTUM CORE v3.3*\n"
        "〰️〰️〰️〰️〰️〰️〰️\n\n"
        f"🔋 *Estado:* `{status_text}` {status_icon}\n"
        f"🎮 *Modo Operativo:* `{mode}`\n"
        f"🔐 *Nivel de Acceso:* `{auth}`\n\n"
        "🚀 *Motor Algorítmico Activo*\n"
        "El sistema está monitoreando el mercado en tiempo real utilizando lógica **Multi-Timeframe (MTF)** y análisis de volatilidad institucional.\n\n"
        "👇 *PANEL DE CONTROL*\n"
        "• `/status` - Dashboard de Mercado\n"
        "• `/risk` - Protocolos de Riesgo\n"
        "• `/help` - Centro de Comandos\n"
    )
    
    bot.edit_message_text(welcome, chat_id=chat_id, message_id=msg_load.message_id, parse_mode='Markdown')

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
    """Muestra estado de grupos y configuración (Fusionado con /config)"""
    chat_id = str(message.chat.id)
    session = session_manager.get_session(chat_id)
    
    # Defaults if no session
    if not session:
        bot.reply_to(message, "⚠️ Sin sesión configurada. Se muestran valores por defecto.")
        mode = "WATCHER (Default)"
        has_keys = False
        leverage = 5
        max_margin = 0.10
        spot_alloc = 0.20
    else:
        cfg = session.get_configuration()
        mode = cfg.get('mode', 'WATCHER')
        has_keys = cfg['has_keys']
        leverage = cfg['leverage']
        max_margin = cfg['max_capital_pct']
        spot_alloc = cfg.get('spot_allocation_pct', 0.20)
    
    # Get F&G
    fg_index = get_fear_and_greed_index()

    # 1. System State
    status = "🕹️ *CENTRO DE MANDO*\n"
    status += "〰️〰️〰️〰️〰️〰️\n"
    status += f"🛡️ *Modo Trading:* `{mode}`\n"
    status += f"🧠 *Sentimiento:* {fg_index}\n"
    status += f"🔌 *Conexión:* {'✅ Estable' if has_keys else '❌ Desconectado'}\n"
    status += "〰️〰️〰️〰️〰️〰️\n"
    
    status += "⚙️ *Configuración Actual:*\n"
    status += f"• *Apalancamiento:* `{leverage}x`\n"
    status += f"• *Margen Máx:* `{max_margin*100:.1f}%`\n"
    status += f"• *Spot Alloc:* `{spot_alloc*100:.1f}%`\n"
    status += f"• *Frecuencia:* {SIGNAL_COOLDOWN/60:.0f} min\n"
    
    status += "\n📡 *Radares Activos:*\n"
    count = 0
    for group, enabled in GROUP_CONFIG.items():
        icon = "✅" if enabled else "🔴"
        display_name = group.replace('_', ' ')
        if enabled: count += len(ASSET_GROUPS.get(group, []))
        status += f"{icon} {display_name}\n"
    
    bot.reply_to(message, status, parse_mode='Markdown')

    bot.reply_to(message, status, parse_mode='Markdown')

@bot.message_handler(commands=['toggle_group', 'togglegroup'])
def handle_toggle_group(message):
    """Ej: /toggle_group CRYPTO"""
    try:
        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message, "⚠️ Uso: `/toggle_group <NOMBRE>` (CRYPTO, STOCKS, COMMODITY)")
            return
            
        target = args[1].upper()
        if target in GROUP_CONFIG:
            GROUP_CONFIG[target] = not GROUP_CONFIG[target]
            state = "ACTIVADO" if GROUP_CONFIG[target] else "DESACTIVADO"
            bot.reply_to(message, f"🔄 Grupo **{target}** ahora está **{state}**.")
        else:
            bot.reply_to(message, f"❌ Grupo no encontrado. Disponibles: {', '.join(GROUP_CONFIG.keys())}")
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")

@bot.message_handler(commands=['resetpilot', 'reset_pilot'])
def handle_reset_pilot(message):
    """Reinicia el contador del Circuit Breaker"""
    chat_id = str(message.chat.id)
    chat_id = str(message.chat.id)
    session = session_manager.get_session(chat_id)
    if not session: 
        bot.reply_to(message, "⚠️ No tienes sesión activa. Usa /set_keys.")
        return

    session.reset_circuit_breaker()
    bot.reply_to(message, "✅ **Circuit Breaker Reiniciado**.\nEl contador de pérdidas consecutivas se ha restablecido a 0.\nPuedes reactivar `/pilot` si lo deseas.", parse_mode='Markdown')

    bot.reply_to(message, "✅ **Circuit Breaker Reiniciado**.\nEl contador de pérdidas consecutivas se ha restablecido a 0.\nPuedes reactivar `/pilot` si lo deseas.", parse_mode='Markdown')

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

# --- CONFIG BTN HANDLERS ---
@threaded_handler
def handle_config(message):
    handle_status(message)

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
            
        # Unpack
        spot = details.get('spot_usdt', 0.0)
        earn = details.get('earn_usdt', 0.0)
        fut_bal = details.get('futures_balance', 0.0)
        fut_pnl = details.get('futures_pnl', 0.0)
        fut_total = details.get('futures_total', 0.0)
        alpaca_native = details.get('alpaca_equity', 0.0)
        
        # Calculate Total Net Worth
        net_worth = spot + earn + fut_total + alpaca_native
        
        # Formatting
        pnl_icon = "🟢" if fut_pnl >= 0 else "🔴"
        
        msg = (
            "🏦 *WALLET REPORT*\n"
            "〰️〰️〰️〰️〰️〰️\n"
            f"💎 *SPOT Capital:* `${spot:,.2f}`\n"
            f"🐷 *EARN (Ahorros):* `${earn:,.2f}`\n"
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
            SYSTEM_CMDS = ['/toggle_group', '/togglegroup', '/set_interval', '/setinterval', '/debug']
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
            elif cmd_part == '/status':
                handle_status(message)
            
            # System (System Only - Filtered above)
            elif cmd_part in ['/toggle_group', '/togglegroup']:
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

                        # Prepare Message
                        msg_text = ""
                        if action_needed == 'OPEN_LONG':
                            msg_text = (
                                f"🚀 *SEÑAL LONG: {asset}*\n"
                                f"Estrategia: Squeeze & Velocity\n"
                                f"Precio: ${m['close']:,.2f}\n"
                                f"Razón: {res['reason_futures']}\n"
                                f"ADX: {m['adx']:.1f}"
                            )
                        elif action_needed == 'OPEN_SHORT':
                            msg_text = (
                                f"📉 *SEÑAL SHORT: {asset}*\n"
                                f"Estrategia: Bearish Breakout\n"
                                f"Precio: ${m['close']:,.2f}\n"
                                f"Razón: {res['reason_futures']}\n"
                                f"ADX: {m['adx']:.1f}"
                            )
                        elif action_needed == 'CLOSE':
                            msg_text = (
                                f"🏁 *SALIDA FUTUROS ({target_side}): {asset}*\n"
                                f"Razón: {res['reason_futures']}"
                            )

                        # Dispatch
                        for session in all_sessions:
                            mode = session.mode
                            cid = session.chat_id
                            
                            try:
                                if mode == 'PILOT':
                                    # AUTO EXECUTE
                                    if action_needed == 'OPEN_LONG':
                                        ok, res_msg = session.execute_long_position(asset, atr=m['atr'])
                                    elif action_needed == 'OPEN_SHORT':
                                        ok, res_msg = session.execute_short_position(asset, atr=m['atr'])
                                    else: # CLOSE
                                        ok, res_msg = session.execute_close_position(asset)
                                        
                                    bot.send_message(cid, f"🤖 *PILOT ACTION*\n{res_msg}", parse_mode='Markdown')
                                        
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


                            # 2. PROCESS ENV CHATS (Watcher Only)
                            for cid in env_chats:
                                if cid not in session_chats:
                                    try:
                                        bot.send_message(cid, msg_text, parse_mode='Markdown')
                                    except: pass

                    except Exception as e:
                        print(f"⚠️ Error procesando {asset}: {e}")
                        
            # --- SAFETY CHECK (Circuit Breaker) ---
            # Runs every loop iteration (approx 60s)
            try:
                all_sessions = session_manager.get_all_sessions()
                for session in all_sessions:
                    triggered, msg = session.check_circuit_breaker()
                    if triggered:
                        bot.send_message(session.chat_id, msg, parse_mode='Markdown')
                        print(f"🚨 Circuit Breaker Triggered for {session.chat_id}")
            except Exception as e:
                print(f"Safety Check Error: {e}")

        except Exception as e:
            print(f"❌ Error CRÍTICO en bucle de trading: {e}")
            
        time.sleep(60)

def start_bot():
    global session_manager
    session_manager = SessionManager()
    
    # Iniciar Trading Thread
    t_trading = threading.Thread(target=run_trading_loop)
    t_trading.daemon = True
    t_trading.start()
    
    # Iniciar Polling
    if bot:
        print("📡 Iniciando Telegram Polling (Main Thread)...")
        
        # Attempt safe startup checks
        try:
            me = bot.get_me()
            print(f"✅ Bot Connected: {me.username} (ID: {me.id})")
            send_alert("✅ *SISTEMA ONLINE* (v3.2.2)\n🚀 Antigravity Activo")
            bot.delete_webhook(drop_pending_updates=True)
        except Exception as e:
            print(f"⚠️ Startup Warning: {e}")

        # Robust Polling Loop
        while True:
            try:
                print("🔄 Starting Infinity Polling (Filters: Message, Callback)...")
                bot.infinity_polling(timeout=10, long_polling_timeout=10, allowed_updates=['message', 'callback_query'])
            
            except Exception as e:
                import traceback
                print(f"❌ Polling Error: {e}")
                # traceback.print_exc() # Optional: reduce log spam
                time.sleep(5)
                print("⚠️ Restarting Polling...")
            
            except BaseException as e:
                print(f"❌ Critical Error (BaseException): {e}")
                time.sleep(5)
                # Check if we should exit on specific signals? 
                # For now, restarting is safer for a worker.
                print("⚠️ Force Restarting...")
    else:
        print("❌ Bot no inicializado.")
        while True:
            time.sleep(10)

if __name__ == "__main__":
    start_bot()
