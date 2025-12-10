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
    'ACCIONES': ['TSLA', 'NVDA', 'MSFT'],
    'MATERIAS_PRIMAS': ['GC=F', 'CL=F']
}

# Estado de los Grupos (Switch ON/OFF)
GROUP_CONFIG = {
    'CRYPTO': True,
    'ACCIONES': True,
    'MATERIAS_PRIMAS': True
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
                    report += f"• {asset}: ❌ Err: `{safe_err}`\n"
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
                
                entry = f"• {asset}: ${m['close']:,.2f} | RSI: {m['rsi']:.1f} {sig_icon}\n"
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

# ... (Handlers remain) ...

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
                        # 1. Obtener Datos
                        df = get_market_data(asset, timeframe='15m', limit=200)
                        if df.empty: continue
                        
                        current_time = time.time()
                        last_alert = last_alert_times.get(asset, 0)
                        
                        # Cooldown check
                        if (current_time - last_alert) < SIGNAL_COOLDOWN:
                            continue
                            
                        # 2. Análisis Híbrido
                        is_spot_buy, spot_metrics = analyze_mean_reversion(df)
                        
                        engine = StrategyEngine(df)
                        fut_result = engine.analyze()
                        fut_signal = fut_result['signal']
                        
                        # 3. Alertas y Estado
                        
                        # SPOT (Independiente de Futuros, siempre avisa si hay señal fuerte)
                        if is_spot_buy:
                            msg = (
                                f"💎 **SEÑAL SPOT: {asset}**\n"
                                f"Estrategia: Reversión a la Media\n"
                                f"Precio: ${spot_metrics['close']:,.2f}\n"
                                f"Razón: {spot_metrics['reason']}"
                            )
                            send_alert(msg)
                            last_alert_times[asset] = current_time
                            # No afectamos pos_state de futuros
                            continue 
                            
                        # FUTUROS (Con Estado para evitar spam de salidas)
                        curr_state = pos_state.get(asset, 'NEUTRAL')
                        
                        if fut_signal == 'BUY':
                            msg = (
                                f"🚀 **SEÑAL FUTUROS: {asset}**\n"
                                f"Estrategia: Squeeze & Velocity\n"
                                f"Precio: ${fut_result['metrics']['close']:,.2f}\n"
                                f"Razón: {fut_result['reason']}\n"
                                f"ADX: {fut_result['metrics']['adx']:.1f} | Squeeze: {'ON' if fut_result['metrics']['squeeze_on'] else 'OFF'}"
                            )
                            send_alert(msg)
                            last_alert_times[asset] = current_time
                            pos_state[asset] = 'LONG' # Actualizar estado
                        
                        elif fut_signal == 'CLOSE_LONG':
                             # SOLO avisar salida si estábamos en LONG (o si no sabemos, una vez)
                             # Para ser seguros: Si estado es NEUTRAL, NO avisar salida (asumimos que ya salimos o nunca entramos)
                             if curr_state == 'LONG':
                                 msg = (
                                    f"📉 **SALIDA FUTUROS: {asset}**\n"
                                    f"Razón: {fut_result['reason']}"
                                 )
                                 send_alert(msg)
                                 last_alert_times[asset] = current_time
                                 pos_state[asset] = 'NEUTRAL' # Resetear estado

                    except Exception as e:
                        print(f"⚠️ Error procesando {asset}: {e}")
                        
        except Exception as e:
            print(f"❌ Error CRÍTICO en bucle de trading: {e}")
            
        time.sleep(60)

def send_welcome(message):
    # Texto en plano para evitar errores de parseo (Markdown legacy es estricto con _)
    help_text = (
        "🤖 ANTIGRAVITY BOT v3.0 - ARQUITECTURA HIBRIDA\n\n"
        "🎮 Control de Mercado\n"
        "/toggle_group <grupo> - Activar/Desactivar Grupos (CRYPTO, ACCIONES, MATERIAS_PRIMAS).\n"
        "/status - Ver estado de Grupos y Estrategias.\n"
        "/set_interval <min> - Ajustar frecuencia de alertas (Cooldown).\n\n"
        
        "📊 Estrategias Duales\n"
        "1. Reversion a la Media (SPOT): Compra en caidas profundas.\n"
        "2. Squeeze & Velocity (FUTUROS): Rupturas de volatilidad explosivas.\n\n"
        
        "⚙️ Configuracion & Riesgo\n"
        "/config - Ver parametros actuales.\n"
        "/set_leverage <x> - Apalancamiento (Futuros).\n"
        "/set_margin <%> - % de Capital por operacion.\n"
        "/set_keys <k> <s> - Registrar API Keys.\n\n"
        
        "📡 Inteligencia\n"
        "/price - Radar de Mercado en Tiempo Real.\n"
        "/pnl - Resultados y PnL."
    )
    bot.reply_to(message, help_text) # Removed parse_mode='Markdown'

def handle_status(message):
    """Muestra estado de grupos y configuración"""
    status = "🕹️ *ESTADO DEL SISTEMA*\n\n"
    
    # Grupos
    status += "*Grupos de Activos:*\n"
    for group, enabled in GROUP_CONFIG.items():
        icon = "✅" if enabled else "🔴"
        status += f"{icon} {group}\n"
        
    status += f"\n*Cooldown de Señal:* {SIGNAL_COOLDOWN/60:.0f} minutos\n"
    status += f"*Activos Vigilados:* {sum(len(v) for k,v in ASSET_GROUPS.items() if GROUP_CONFIG[k])}"
    
    bot.reply_to(message, status, parse_mode='Markdown')

def handle_toggle_group(message):
    """Ej: /toggle_group CRYPTO"""
    try:
        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message, "⚠️ Uso: `/toggle_group <NOMBRE>` (CRYPTO, ACCIONES, etc)")
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
        f"🔑 *API Binance:* {'✅ Conectado' if cfg['has_keys'] else '❌ Desconectado'}\n"
        f"🌍 *Proxy:* {proxy_status}\n"
        f"🕹️ *Apalancamiento:* {cfg['leverage']}x\n"
        f"💰 *Margen Máx:* {cfg['max_capital_pct']*100:.1f}%\n"
        f"🛡️ *Stop Loss:* {cfg['stop_loss_pct']*100:.1f}%\n\n"
        "Para editar: `/set_leverage`, `/set_margin`, `/set_keys`."
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
        bot.reply_to(message, f"✅ Leverage: {val}x")
    except: bot.reply_to(message, "Error.")

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
        bot.reply_to(message, f"✅ Margen: {val*100}%")
    except: bot.reply_to(message, "Error.")

def handle_pnlrequest(message):
    chat_id = str(message.chat.id)
    session = session_manager.get_session(chat_id)
    if not session: 
        bot.reply_to(message, "Sin sesión.")
        return
    
    pnl, _ = session.get_pnl_history()
    avail, total = session.get_balance_details()
    bot.reply_to(message, f"💰 *PnL (24h):* ${pnl:.2f}\n💳 *Balance:* ${avail:.2f} / ${total:.2f}", parse_mode='Markdown')


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
            
            # Mapa de comandos
            if cmd_part in ['/start', '/help']:
                send_welcome(message)
            elif cmd_part == '/status':
                handle_status(message)
            elif cmd_part == '/toggle_group':
                handle_toggle_group(message)
            elif cmd_part in ['/set_interval', '/set_cooldown']:
                handle_set_interval(message)
            elif cmd_part == '/set_proxy':
                handle_set_proxy(message)
            elif cmd_part == '/config':
                handle_config(message)
            elif cmd_part == '/price':
                handle_price(message)
            elif cmd_part == '/set_keys':
                handle_set_keys(message)
            elif cmd_part == '/debug':
                handle_debug(message)
            elif cmd_part == '/set_leverage':
                handle_set_leverage(message)
            elif cmd_part == '/set_margin':
                handle_set_margin(message)
            elif cmd_part == '/pnl':
                handle_pnlrequest(message)
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
