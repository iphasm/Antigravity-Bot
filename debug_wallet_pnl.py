
import os
import sys
from dotenv import load_dotenv
from utils.trading_manager import SessionManager

# Load Env
load_dotenv()

# Setup Session Manager
try:
    sm = SessionManager('data/sessions.json')
    # Get first session ID
    sessions = sm.sessions
    if not sessions:
        print("❌ No active sessions found in data/sessions.json")
        sys.exit()
    
    chat_id = list(sessions.keys())[0]
    session = sessions[chat_id]
    client = session.client
    
    if not client:
        print(f"❌ Session found for {chat_id} but Client is None")
        sys.exit()
        
    print(f"✅ Using Session for Chat ID: {chat_id}")
    
except Exception as e:
    print(f"❌ Error loading session: {e}")
    sys.exit()

print("\n--- 1. TESTING EARN (Flexible) ---")
try:
    # Try Simple Earn Flexible
    flex_pos = client.get_simple_earn_flexible_position()
    print(f"Flexible Positions Found: {len(flex_pos)}")
    for p in flex_pos:
        print(f" - {p['asset']}: {p['totalAmount']}")
except Exception as e:
    print(f"❌ Error Flexible: {e}")

print("\n--- 2. TESTING EARN (Locked) ---")
try:
    # Try Simple Earn Locked
    locked_pos = client.get_simple_earn_locked_position()
    print(f"Locked Positions Found: {len(locked_pos)}")
    for p in locked_pos:
        print(f" - {p['asset']}: {p['totalAmount']}")
except Exception as e:
    print(f"❌ Error Locked: {e}")

print("\n--- 3. TESTING PNL (Futures) ---")
try:
    # Check Income History for REALIZED_PNL
    income = client.futures_income_history(incomeType='REALIZED_PNL', limit=10)
    print(f"PnL Entries Found: {len(income)}")
    for i in income:
        print(f" - {i['symbol']} ({i['time']}): {i['income']}")
except Exception as e:
    print(f"❌ Error PnL: {e}")
