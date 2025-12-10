import os
import telebot
import time
from dotenv import load_dotenv

def check_connection():
    print("🔍 DIAGNOSTIC: Checking Telegram Connection...")
    
    # 1. Load Env
    load_dotenv()
    token = os.getenv('TELEGRAM_TOKEN')
    
    if not token:
        print("❌ ERROR: TELEGRAM_TOKEN is missing in environment.")
        return
        
    print(f"✅ Token found: {token[:5]}...{token[-5:]}")
    
    # 2. Initialize Bot
    try:
        bot = telebot.TeleBot(token)
        user = bot.get_me()
        print(f"✅ Connection Successful!")
        print(f"🤖 Bot Name: {user.first_name}")
        print(f"🤖 Bot Username: @{user.username}")
        print(f"🆔 Bot ID: {user.id}")
        
    except Exception as e:
        print(f"❌ Connection Failed: {e}")
        print("💡 Possible causes: Invalid Token, Proxy issues, DNS/Internet down.")

if __name__ == "__main__":
    check_connection()
