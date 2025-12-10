import time
import os
import threading
import telebot
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

def resolve_symbol(text):
    """Clean and standardize input symbol. Auto-appends USDT if needed."""
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
        # 1. Obtener Datos
        df = get_market_data(asset, timeframe='15m', limit=200)
        if df.empty: 
            return False, "No Data"
        
        # 2. Análisis Unificado (Spot + Futuros)
        engine = StrategyEngine(df)
        analysis_result = engine.analyze()
        
        return True, analysis_result
        
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

def handle_price(message):
    try:
        sent = bot.reply_to(message, "⏳ Escaneando mercado con Motores Híbridos...")
        
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

def handle_manual_closeall(message):
    """ /closeall """
    chat_id = str(message.chat.id)
    session = session_manager.get_session(chat_id)
    if not session: return
    
    bot.reply_to(message, "🚨 Ejecutando CLOSE ALL...")
    success, msg = session.execute_close_all()
    bot.reply_to(message, msg)

def send_welcome(message):
    # Texto en plano para evitar errores de parseo (Markdown legacy es estricto con _)
    help_text = (
        "🤖 ANTIGRAVITY BOT v3.2 - COMMAND LIST\n\n"
        "🎮 *CONTROL GENERAL*\n"
        "• /start - Verificar Estado y Conexión.\n"
        "• /status - Ver estado del sistema y modo de riesgo.\n"
        "• /toggle_group <GRUPO> - Activar/Desactivar (CRYPTO, STOCKS, COMMODITY).\n"
        "• /set_interval <MIN> - Ajustar frecuencia de análisis.\n"
        "• /debug - Diagnóstico completo de conexión y claves.\n\n"
        
        "🔫 *TRADING MANUAL (FUTUROS)*\n"
        "• /long <TICKER> - Abrir LONG (Ej: `/long BTC`).\n"
        "• /sell <TICKER> - Smart Sell (Cierra Long o Abre Short).\n"
        "• /close <TICKER> - Cerrar posición específica.\n"
        "• /closeall - CERRAR TODO (Botón de Pánico).\n\n"
        
        "🛡️ *GESTIÓN Y RIESGO*\n"
        "• /risk - Explicación detallada del modelo de Riesgo.\n"
        "• /config - Ver tu apalancamiento y margen.\n"
        "• /wallet - Ver Capital Spot, Balance Futuros y PnL Total.\n"
        "• /pnl - Reporte de rendimiento (24h).\n"
        "• /set_leverage <X> - Cambiar apalancamiento (Ej: 10).\n"
        "• /set_margin <%> - Límite asignación (Ej: 0.1 para 10%).\n"
        "• /set_keys <KEY> <SECRET> - Configurar API Binance.\n\n"
        
        "📡 *INTELIGENCIA*\n"
        "• /price - Radar de precios y señales técnicas."
    )
    try:
        bot.reply_to(message, help_text, parse_mode='Markdown')
    except Exception as e:
        # Fallback to plain text if Markdown fails (usually due to bad char or syntax)
        print(f"⚠️ Error enviando Help (Markdown): {e}")
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
        "🛡️ *SISTEMA DE GESTIÓN DE RIESGO AVANZADO*\n"
        "〰️〰️〰️〰️〰️〰️\n"
        "1. *Stop Loss Dinámico (ATR)*\n"
        "   El bot analiza la volatilidad (Average True Range). \n"
        "   • *Distancia SL:* `2.0 x ATR` (Se aleja si hay ruido, se acerca si hay calma).\n"
        "   • *Objetivo:* Evitar barridas de stop en mercados volátiles.\n\n"
        
        "2. *Cálculo de Posición (Sizing)*\n"
        "   El tamaño de la operación NO es fijo. Se calcula para arriesgar máx un **2%** de tu capital por trade.\n"
        "   • *Fórmula:* `Capital * 0.02 / Distancia_SL`\n"
        "   • *Límite de Seguridad:* Nunca superará el Margin Global configurado (actual: **{margin}**).\n\n"
        
        "3. *Take Profit Dividido (Split)*\n"
        "   • *TP1 (50%):* Se cierra al alcanzar **1.5R** (Retorno/Riesgo). Asegura ganancias rápido.\n"
        "   • *TP2 (50%):* Activa un **Trailing Stop** del 1.5%. Si el precio sigue subiendo, el bot lo persigue para maximizar la ganancia.\n\n"
        
        "ℹ️ _Si la volatilidad (ATR) no está disponible, el sistema usa el modo 'Fallback' (SL {sl_fixed} fijo)._"
    ).format(margin=margin, sl_fixed=sl_fixed)
    
    bot.reply_to(message, msg, parse_mode='Markdown')

def handle_start(message):
    """Simple Health Check & Intro"""
    bot.reply_to(message, "⏳ Iniciando sistemas...")
    
    # Quick Check
    status = "✅ *ONLINE*\n"
    if not bot.get_me():
        status = "⚠️ *CONEXIÓN INESTABLE*"
        
    chat_id = str(message.chat.id)
    session = session_manager.get_session(chat_id)
    
    auth_status = "❌ Sin Llaves"
    if session and session.client:
        auth_status = "✅ Autenticado"
        
    msg = (
        "🤖 *ANTIGRAVITY BOT v3.2*\n"
        f"Estado: {status}\n"
        f"API: {auth_status}\n\n"
        "Comandos: `/help`\n"
        "Configuración: `/config`\n"
        "Diagnóstico: `/debug`"
    )
    bot.reply_to(message, msg, parse_mode='Markdown')

def handle_status(message):
    """Muestra estado de grupos y configuración"""
    status = "🕹️ *ESTADO DEL SISTEMA*\n\n"
    
    status += f"*Activos Vigilados:* {sum(len(v) for k,v in ASSET_GROUPS.items() if GROUP_CONFIG[k])}\n"
    status += f"*Cooldown de Señal:* {SIGNAL_COOLDOWN/60:.0f} minutos\n"
    status += f"*Threads Activos:* {threading.active_count()}\n"
    status += "🤖 *Motor:* Antigravity v3.2 (Hybrid Engine)"
    
    bot.reply_to(message, status, parse_mode='Markdown')

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

def handle_set_proxy(message):
    bot.reply_to(message, "❌ El proxy se gestiona automáticamente desde Railway (Variables de Entorno).")

def handle_set_keys(message):
    """Configura API Keys: /set_keys <KEY> <SECRET>"""
    chat_id = str(message.chat.id)
    try:
        args = message.text.split()
        if len(args) != 3:
            bot.reply_to(message, "⚠️ Uso: `/set_keys <API_KEY> <API_SECRET>`\n(Te recomendamos borrar el mensaje después)", parse_mode='Markdown')
            return
            
        key = args[1]
        secret = args[2]
        
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

def handle_config(message):
    chat_id = str(message.chat.id)
    session = session_manager.get_session(chat_id)
    
    if not session:
        bot.reply_to(message, "❌ Sesión no encontrada. Usa `/set_keys`.")
        return

    cfg = session.get_configuration()
    
    # Global Proxy Check
    sys_proxy = os.getenv('PROXY_URL')
    proxy_status = "✅ Activado (Global)" if sys_proxy else "🔴 Apagado"
    
    msg = (
        "⚙️ *CONFIGURACIÓN PERSONAL*\n\n"
        f"🔑 *API:* {'✅ Vinculada' if cfg['has_keys'] else '❌ Sin Vincular'}\n"
        "〰️〰️〰️〰️〰️〰️\n"
        "📡 *Grupos Activos (Scanner):*\n"
    )
    
    for group, enabled in GROUP_CONFIG.items():
        icon = "✅" if enabled else "🔴"
        display_name = group.replace('_', ' ')
        msg += f"{icon} {display_name}\n"
    
    msg += (
        "〰️〰️〰️〰️〰️〰️\n"
        f"🕹️ *Apalancamiento:* {cfg['leverage']}x\n"
        f"💰 *Margen Máx:* {cfg['max_capital_pct']*100:.1f}%\n"
        f"🛡️ *Stop Loss:* {cfg['stop_loss_pct']*100:.1f}% (Fallback)\n"
        "〰️〰️〰️〰️〰️〰️\n"
        "ℹ️ _Para cambiar:_\n"
        "• `/set_leverage <x>`\n"
        "• `/set_margin <0.1>`"
    )
    bot.reply_to(message, msg, parse_mode='Markdown')

def handle_set_leverage(message):
    chat_id = str(message.chat.id)
    session = session_manager.get_session(chat_id)
    if not session: return
    try:
        val = int(message.text.split()[1])
        session.update_config('leverage', val)
        session_manager.save_sessions()
        bot.reply_to(message, f"✅ *Palanca Ajustada:* {val}x")
    except: bot.reply_to(message, "❌ Error: Usa `/set_leverage 10`")

def handle_debug(message):
    """Generates a System Diagnostics Report"""
    sent = bot.reply_to(message, "🔍 Ejecutando diagnóstico de sistema...")
    chat_id = str(message.chat.id)
    session = session_manager.get_session(chat_id)
    
    # 1. System Info
    py_ver = platform.python_version()
    os_plat = platform.system()
    
    # 2. Credentials
    has_key = "✅" if session and session.api_key else "❌"
    has_sec = "✅" if session and session.api_secret else "❌"
    masked_key = f"{session.api_key[:4]}...{session.api_key[-4:]}" if session and session.api_key else "N/A"
    
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
    
    # 4. Binance Public
    try:
        t0 = time.time()
        btc_data = get_market_data('BTCUSDT', limit=1)
        ping_ms = int((time.time() - t0) * 1000)
        
        if not btc_data.empty:
            btc_price = btc_data.iloc[-1]['close']
            pub_status = f"✅ Success (BTC: {btc_price:.2f})"
        else:
            pub_status = "⚠️ Data Empty"
            
        ping_status = f"✅ Success ({ping_ms}ms)"
    except Exception as e:
        pub_status = f"❌ Failed: {str(e)}"
        ping_status = "❌ Failed"
        
    # 5. Binance Private
    auth_status = "❌ No Session"
    can_trade = "Unknown"
    acc_type = "Unknown"
    bal_usdt = "0.00"
    
    if session and session.client:
        try:
            # Simple auth check
            acc = session.client.futures_account()
            auth_status = "✅ Auth Success!"
            can_trade = str(acc.get('canTrade', False))
            acc_type = "FUTURES" # We are using futures client
            bal_usdt = next((float(a['availableBalance']) for a in acc.get('assets', []) if a['asset']=='USDT'), 0.0)
            bal_usdt = f"{bal_usdt:.2f}"
        except Exception as e:
            auth_status = "❌ Auth Failed"
            can_trade = f"Error: {str(e)}"
    
    report = (
        "🔍 *SYSTEM DIAGNOSTICS REPORT* 🔍\n\n"
        f"Python Version: {py_ver}\n"
        f"Platform: {os_plat}\n\n"
        
        "🔑 *Credentials Check:*\n"
        f"- API Key Present: {has_key}\n"
        f"- API Key Masked: {masked_key}\n"
        f"- Secret Present: {has_sec}\n\n"
        
        "🌍 *Network / IP Check:*\n"
        f"🔄 Proxy Configured: {proxy_conf}\n"
        f"- Effective IP: {eff_ip}\n"
        f"- Location: {loc}\n\n"
        
        f"{loc_check} Location looks good (Not US).\n\n"
        
        "📡 *Binance Public API:*\n"
        f"{ping_status}\n"
        f"Data Fetch: {pub_status}\n\n"
        
        "🔐 *Binance Authenticated API:*\n"
        f"{auth_status}\n"
        f"- Can Trade: {can_trade}\n"
        f"- Account Type: {acc_type}\n"
        f"- Futures USDT Balance: {bal_usdt}"
    )
    
    bot.edit_message_text(report, chat_id=sent.chat.id, message_id=sent.message_id, parse_mode='Markdown')

def handle_set_margin(message):
    chat_id = str(message.chat.id)
    session = session_manager.get_session(chat_id)
    if not session: return
    try:
        val = float(message.text.split()[1])
        session.update_config('max_capital_pct', val)
        session_manager.save_sessions()
        bot.reply_to(message, f"✅ *Margen Máximo Global:* {val*100:.1f}%\nℹ️ _Límite de seguridad para asignación total._")
    except: bot.reply_to(message, "❌ Error: Usa `/set_margin 0.1` (10%)")

def handle_pnlrequest(message):
    chat_id = str(message.chat.id)
    session = session_manager.get_session(chat_id)
    if not session: 
        bot.reply_to(message, "⚠️ Sin sesión activa.")
        return
    
    # Obtener datos
    pnl, _ = session.get_pnl_history() # Simulado o real según implementación
    avail, total = session.get_balance_details()
    
    # Determinar iconos
    icon = "🟢" if pnl >= 0 else "🔴"
    
    msg = (
        "� *REPORTE DE RENDIMIENTO (24h)*\n"
        "〰️〰️〰️〰️〰️〰️\n"
        f"💰 *PnL Realizado:* {icon} `${pnl:,.2f}`\n"
        "〰️〰️〰️〰️〰️〰️\n"
        f"💳 *Balance Disponible:* `${avail:,.2f}`\n"
        f"🏦 *Balance Total:* `${total:,.2f}`"
    )
    bot.reply_to(message, msg, parse_mode='Markdown')

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
            elif cmd_part == '/config':
                handle_config(message)
            elif cmd_part == '/price':
                handle_price(message)
            elif cmd_part == '/set_keys':
                handle_set_keys(message)
            elif cmd_part == '/set_leverage':
                handle_set_leverage(message)
            elif cmd_part == '/set_margin':
                handle_set_margin(message)
            elif cmd_part == '/pnl':
                handle_pnlrequest(message)
            elif cmd_part == '/wallet':
                handle_wallet(message)
            elif cmd_part == '/set_proxy':
                handle_set_proxy(message)
            
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
    
    while True:
        try:
            # Iterar Grupos Activos
            for group_name, assets in ASSET_GROUPS.items():
                if not GROUP_CONFIG.get(group_name, False):
                    continue
                    
                for asset in assets:
                    try:
                        current_time = time.time()
                        last_alert = last_alert_times.get(asset, 0)
                        
                        # Cooldown check
                        if (current_time - last_alert) < SIGNAL_COOLDOWN:
                            continue

                        # 1. Procesar Activo (Unified)
                        success, res = process_asset(asset)
                        if not success: continue
                        
                        m = res['metrics']
                        
                        # 2. Alertas
                        
                        # SPOT ALERT
                        if res['signal_spot']:
                            msg = (
                                f"💎 *SEÑAL SPOT: {asset}*\n"
                                f"Estrategia: Reversión a la Media\n"
                                f"Precio: ${m['close']:,.2f}\n"
                                f"Razón: {res['reason_spot']}"
                            )
                            send_alert(msg)
                            last_alert_times[asset] = current_time
                            continue # Si es Spot, enviamos y pasamos (no mezclamos con Futuros por ahora)
                            
                        # FUTUROS ALERTS (Con State)
                        curr_state = pos_state.get(asset, 'NEUTRAL')
                        fut_sig = res['signal_futures']
                        
                        if fut_sig == 'BUY':
                            msg = (
                                f"🚀 *SEÑAL FUTUROS: {asset}*\n"
                                f"Estrategia: Squeeze & Velocity\n"
                                f"Precio: ${m['close']:,.2f}\n"
                                f"Razón: {res['reason_futures']}\n"
                                f"ADX: {m['adx']:.1f} | Squeeze: {'ON' if m['squeeze_on'] else 'OFF'}"
                            )
                            send_alert(msg)
                            last_alert_times[asset] = current_time
                            pos_state[asset] = 'LONG'
                        
                        elif fut_sig == 'CLOSE_LONG':
                             if curr_state == 'LONG':
                                 msg = (
                                    f"📉 *SALIDA FUTUROS: {asset}*\n"
                                    f"Razón: {res['reason_futures']}"
                                 )
                                 send_alert(msg)
                                 last_alert_times[asset] = current_time
                                 pos_state[asset] = 'NEUTRAL'

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
        try:
            send_alert("✅ *SISTEMA DEPURADO Y LISTO (MANUAL DISPATCH)*\nEnvía /start o /help para probar.")
            
            bot.delete_webhook(drop_pending_updates=True)
            bot.infinity_polling(timeout=10, long_polling_timeout=10, allowed_updates=['message'])
            
        except Exception as e:
            print(f"❌ Polling Error: {e}")
            time.sleep(5)
    else:
        print("❌ Bot no inicializado.")
        while True:
            time.sleep(10)

if __name__ == "__main__":
    start_bot()
