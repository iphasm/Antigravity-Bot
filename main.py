import time
import os
import threading
import telebot
import logging
from dotenv import load_dotenv

# Importar módulos internos
from data.fetcher import get_market_data
from strategies.analyzer import analyze_mean_reversion
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

# --- HANDLERS (SIN DECORADORES, LLAMADOS POR MASTER) ---

def send_welcome(message):
    help_text = (
        "🤖 **ANTIGRAVITY BOT v3.0 - ARQUITECTURA HÍBRIDA**\n\n"
        "**🎮 Control de Mercado**\n"
        "`/toggle_group <grupo>` — Activar/Desactivar Grupos (CRYPTO, ACCIONES, MATERIAS_PRIMAS).\n"
        "`/status` — Ver estado de Grupos y Estrategias.\n"
        "`/set_interval <min>` — Ajustar frecuencia de alertas (Cooldown).\n\n"
        
        "**📊 Estrategias Duales**\n"
        "1️⃣ **Reversión a la Media (SPOT)**: Compra en caídas profundas.\n"
        "2️⃣ **Squeeze & Velocity (FUTUROS)**: Rupturas de volatilidad explosivas.\n\n"
        
        "**⚙️ Configuración & Riesgo**\n"
        "`/config` — Ver parámetros actuales (incluyendo Proxy).\n"
        "`/set_proxy <url>` — Configurar HTTP Proxy para Binance.\n"
        "`/set_leverage <x>` — Apalancamiento (Futuros).\n"
        "`/set_margin <%>` — % de Capital por operación.\n"
        "`/set_keys` — Registrar API Keys.\n\n"
        
        "**📡 Inteligencia**\n"
        "`/price` — Radar de Mercado en Tiempo Real.\n"
        "`/pnl` — Resultados y PnL."
    )
    bot.reply_to(message, help_text, parse_mode='Markdown')

def handle_status(message):
    """Muestra estado de grupos y configuración"""
    status = "🕹️ **ESTADO DEL SISTEMA**\n\n"
    
    # Grupos
    status += "**Grupos de Activos:**\n"
    for group, enabled in GROUP_CONFIG.items():
        icon = "✅" if enabled else "🔴"
        status += f"{icon} {group}\n"
        
    status += f"\n**Cooldown de Señal:** {SIGNAL_COOLDOWN/60:.0f} minutos\n"
    status += f"**Activos Vigilados:** {sum(len(v) for k,v in ASSET_GROUPS.items() if GROUP_CONFIG[k])}"
    
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
    """Configura el proxy para la sesión"""
    chat_id = str(message.chat.id)
    session = session_manager.get_session(chat_id)
    if not session:
        bot.reply_to(message, "⛔ Sin sesión. Usa `/set_keys` primero.")
        return

    try:
        args = message.text.split()
        if len(args) < 2:
            bot.reply_to(message, "⚠️ Uso: `/set_proxy <http://user:pass@ip:port>` o `/set_proxy off`")
            return
            
        url = args[1]
        if url.lower() == 'off':
            session.update_config('proxy_url', None)
            bot.reply_to(message, "🌍 Proxy **DESACTIVADO**.")
        else:
            session.update_config('proxy_url', url)
            bot.reply_to(message, "🌍 Proxy **CONFIGURADO**. Reiniciando cliente...")
        
        session_manager.save_sessions()
        session._init_client()
        
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {e}")

def handle_config(message):
    chat_id = str(message.chat.id)
    session = session_manager.get_session(chat_id)
    
    if not session:
        bot.reply_to(message, "❌ Sesión no encontrada.")
        return

    cfg = session.get_configuration()
    
    msg = (
        "⚙️ **CONFIGURACIÓN PERSONAL**\n\n"
        f"🔑 **API Binance:** {'✅ Conectado' if cfg['has_keys'] else '❌ Desconectado'}\n"
        f"🌍 **Proxy:** {'✅ Activado' if cfg['proxy_enabled'] else '🔴 Apagado'}\n"
        f"🕹️ **Apalancamiento:** {cfg['leverage']}x\n"
        f"💰 **Margen Máx:** {cfg['max_capital_pct']*100:.1f}%\n"
        f"🛡️ **Stop Loss:** {cfg['stop_loss_pct']*100:.1f}%\n\n"
        "Para editar: `/set_leverage`, `/set_margin`, `/set_proxy`."
    )
    bot.reply_to(message, msg, parse_mode='Markdown')

def handle_price(message):
    bot.reply_to(message, "⏳ Escaneando mercado con Motores Híbridos...")
    
    report = "📡 **RADAR DE MERCADO (SPOT + FUTUROS)**\n\n"
    
    # Check Groups
    active_groups = [g for g, active in GROUP_CONFIG.items() if active]
    if not active_groups:
        bot.reply_to(message, "⚠️ Todos los grupos están desactivados. Usa `/toggle_group`.")
        return

    for group_name in active_groups:
        assets = ASSET_GROUPS.get(group_name, [])
        report += f"**{group_name}**\n"
        
        for asset in assets:
            try:
                df = get_market_data(asset, timeframe='15m', limit=200)
                if df.empty: continue
                
                # Ejecutar Motor Híbrido solo para métricas
                # 1. Spot (Mean Reversion)
                is_mr, mr_metrics = analyze_mean_reversion(df)
                
                # 2. Futuros (Strategy Engine)
                engine = StrategyEngine(df)
                fut_res = engine.analyze()
                
                price = df.iloc[-1]['close']
                rsi = df.iloc[-1]['rsi']
                
                # Iconos de señal
                sig_icon = ""
                if is_mr: sig_icon += "💎 SPOT BUY "
                if fut_res['signal'] == 'BUY': sig_icon += "🚀 FUT LONG"
                
                entry = f"• {asset}: ${price:,.2f} | RSI: {rsi:.1f} {sig_icon}\n"
                report += entry
                
            except Exception:
                continue
        report += "\n"
        
    bot.send_message(message.chat.id, report, parse_mode='Markdown')

def handle_set_keys(message):
    chat_id = str(message.chat.id)
    try:
        args = message.text.split()
        if len(args) < 3:
            bot.reply_to(message, "⚠️ Uso: `/set_keys <API_KEY> <API_SECRET>`")
            return
        session = session_manager.create_or_update_session(chat_id, args[1], args[2])
        status = "✅ Conectado" if session.client else "⚠️ Keys guardadas (Sin conexión)"
        bot.reply_to(message, f"{status}")
    except Exception as e:
        bot.reply_to(message, f"Error: {e}")

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
    bot.reply_to(message, f"💰 **PnL (24h):** ${pnl:.2f}\n💳 **Balance:** ${avail:.2f} / ${total:.2f}", parse_mode='Markdown')


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
                        
                        # 3. Alertas
                        if is_spot_buy:
                            msg = (
                                f"💎 **SEÑAL SPOT: {asset}**\n"
                                f"Estrategia: Reversión a la Media\n"
                                f"Precio: ${spot_metrics['close']:,.2f}\n"
                                f"Razón: {spot_metrics['reason']}"
                            )
                            send_alert(msg)
                            last_alert_times[asset] = current_time
                            continue 
                            
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
                        
                        elif fut_signal == 'CLOSE_LONG':
                             msg = (
                                f"📉 **SALIDA FUTUROS: {asset}**\n"
                                f"Razón: {fut_result['reason']}"
                             )
                             send_alert(msg)
                             last_alert_times[asset] = current_time

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
            send_alert("✅ **SISTEMA DEPURADO Y LISTO (MANUAL DISPATCH)**\nEnvía /start o /help para probar.")
            
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
