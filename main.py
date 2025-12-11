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
    'CRYPTO': ['BTCUSDT', 'ETHUSDT', 'XRPUSDT', 'SOLUSDT', 'SUIUSDT', 'ZECUSDT'],
    'STOCKS': ['TSLA', 'NVDA', 'MSFT', 'AAPL', 'AMD'],
    'COMMODITY': ['GLD', 'USO'] # ETFs for Alpaca (Gold, Oil)
}

# Mapping de nombres amigables
TICKER_MAP = {
    'BTCUSDT': 'Bitcoin',
    'ETHUSDT': 'Ethereum',
    'XRPUSDT': 'Ripple',
    'SOLUSDT': 'Solana',
    'SUIUSDT': 'Sui',
    'ZECUSDT': 'Zcash',
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
    s = text.strip().upper()
    
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
    session = session_manager.get_session(chat_id)
    if not session: return

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
    session = session_manager.get_session(chat_id)
    if not session: return

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
    session = session_manager.get_session(chat_id)
    if not session: return
    
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

# --- MASTER LISTENER ---
@bot.message_handler(func=lambda m: True)
def master_listener(message):
    """Recibe TODO y despacha"""
    try:
        text = message.text
        if not text: return
        
        print(f"📨 DEBUG: Recibido '{text}' de {message.chat.id}")
        
        if text.startswith('/'):
            cmd_part = text.split()[0].lower()
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
            SYSTEM_CMDS = ['/toggle_group', '/set_interval', '/debug']
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
            
            # System (Admin Only - Filtered above)
            elif cmd_part == '/toggle_group':
                handle_toggle_group(message)
            elif cmd_part in ['/set_interval', '/set_cooldown']:
                handle_set_interval(message)
            elif cmd_part == '/debug':
                handle_debug(message)
            

            # User Config & Trading (Allowed for Subscribers)
            elif cmd_part in ['/config', '/status']: # Alias /config to /status
                handle_status(message)
            elif cmd_part == '/price':
                handle_price(message)
            elif cmd_part == '/set_keys':
                handle_set_keys(message)
            elif cmd_part == '/set_leverage':
                handle_set_leverage(message)
            elif cmd_part == '/set_margin':
                handle_set_margin(message)
            elif cmd_part == '/set_spot_alloc':
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
            elif cmd_part == '/sell':
                handle_manual_sell(message)
            elif cmd_part == '/close':
                handle_manual_close(message)
            elif cmd_part == '/closeall':
                handle_manual_closeall(message)
            else:
               bot.reply_to(message, "🤷‍♂️ Comando desconocido.")

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
                                    bot.send_message(cid, f"{base_msg}\n\n🤖 *PILOT ACTION:*\n{status_icon} {info}", parse_mode='Markdown')
                                    
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
