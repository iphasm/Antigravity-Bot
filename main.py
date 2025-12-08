import time
import os
import threading
import telebot
from dotenv import load_dotenv

# Import internal modules
from data.fetcher import get_market_data
from strategies.analyzer import analyze_market

# Load environment variables
load_dotenv()

# --- CONFIGURATION ---
WATCHLIST = [
    'BTC-USD', 'ETH-USD', 'SOL-USD', 'XRP-USD', 
    'ADA-USD', 'SUI-USD', 'PEPE-USD', 
    'MSFT', 'TSLA', 'GC=F']
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

# Initialize Bot
bot = None
if TELEGRAM_TOKEN:
    bot = telebot.TeleBot(TELEGRAM_TOKEN)
else:
    print("WARNING: TELEGRAM_TOKEN not found.")

def send_alert(message):
    """Wrapper to send messages using TeleBot instance"""
    if bot and TELEGRAM_CHAT_ID:
        try:
            bot.send_message(TELEGRAM_CHAT_ID, message, parse_mode='Markdown')
        except Exception as e:
            print(f"Error sending alert: {e}")
    else:
        print(f"ALERT (No Telegram): {message}")

# --- BOT COMMAND HANDLERS ---

@bot.message_handler(commands=['price', 'precios'])
def handle_price_request(message):
    """Handles /price command to show current status of all assets"""
    user_id = str(message.chat.id)
    
    # Optional: Security check to only reply to owner
    if TELEGRAM_CHAT_ID and user_id != str(TELEGRAM_CHAT_ID):
        bot.reply_to(message, "⛔ Unauthorized.")
        return

    bot.reply_to(message, "⏳ Fetching prices... please wait.")
    
    report = "📊 **MARKET REPORT**\n\n"
    
    for asset in WATCHLIST:
        try:
            # Fetch sufficient data for RSI (limit=100) instead of just 5
            df = get_market_data(asset, timeframe='15m', limit=100)
            
            if df.empty:
                report += f"❌ {asset}: No data\n"
                continue
                
            # Get latest close
            latest = df.iloc[-1]
            price = latest['close']
            
            # Simple RSI calculation for context (optional, reuse analyzer if inexpensive)
            # Re-running full analysis might be heavy, but let's do it for consistency
            _, metrics = analyze_market(df)
            rsi = metrics.get('rsi', 0)
            
            report += f"💎 **{asset}**\n💰 ${price:.2f} | 📉 RSI: {rsi:.1f}\n\n"
            
        except Exception as e:
            report += f"⚠️ {asset}: Error ({str(e)[:20]}...)\n"
    
    bot.send_message(message.chat.id, report, parse_mode='Markdown')

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    bot.reply_to(message, "🤖 **Trading Bot Active**\n\nCommands:\n/price - Get current market prices")

# --- MAIN TRADING LOOP ---

def trading_loop():
    print("🚀 Trading Loop Started (60s interval)...")
    cycle_count = 0
    
    while True:
        cycle_count += 1
        
        # Heartbeat: Send message every 60 minutes (60 cycles)
        if cycle_count % 60 == 0:
            send_alert(f"🟢 **STATUS REPORT**\nBot online. Scan cycle: {cycle_count}")
        
        for asset in WATCHLIST:
            try:
                # 1. Fetch Data
                df = get_market_data(asset, timeframe='15m', limit=100)
                
                if df.empty:
                    print(f"Skipping {asset}: No data.")
                    continue

                # 2. Analyze
                buy_signal, metrics = analyze_market(df)
                
                # 3. Alert
                if buy_signal:
                    price = metrics.get('close', 0)
                    rsi = metrics.get('rsi', 0)
                    print(f"🚨 BUY SIGNAL: {asset} | Price: {price:.2f} | RSI: {rsi:.2f}")
                    
                    msg = f"🚀 *SEÑAL DE COMPRA DETECTADA* \n\n💎 Activo: {asset}\n💰 Precio: {price:.2f}\n📉 RSI: {rsi:.2f}"
                    send_alert(msg)
            
            except Exception as e:
                print(f"Error processing {asset}: {e}")
        
        print("--- Cycle complete. Waiting 60s ---")
        time.sleep(60)

# --- ENTRY POINT ---

def start_bot():
    # 1. Start Telegram Polling in a separate thread
    if bot:
        print("📡 Starting Telegram Polling...")
        # infinity_polling avoids some crashes on network errors
        t = threading.Thread(target=bot.infinity_polling, kwargs={'interval': 1, 'timeout': 20}) 
        t.daemon = True # Ends when main thread ends
        t.start()
    
    # 2. Run Trading Loop in main thread
    trading_loop()

if __name__ == "__main__":
    try:
        start_bot()
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user.")
