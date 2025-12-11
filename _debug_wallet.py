import os
import json
from binance.client import Client
from dotenv import load_dotenv

load_dotenv()

def debug_wallet():
    print("🔍 DEBUGGING WALLET BALANCES")
    
    # 1. Load Sessions
    file_path = 'data/sessions.json'
    sessions = {}
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            try:
                sessions = json.load(f)
            except: 
                print("⚠️ Corrupt JSON")
        
    print(f"Found {len(sessions)} sessions in file.")
    
    # 2. Iterate and Check (File Sessions)
    for chat_id, data in sessions.items():
        print(f"\n👤 Checking Session: {chat_id}")
        api_key = data.get('api_key')
        api_secret = data.get('api_secret')
        
        if not api_key or not api_secret:
            continue
            
        check_balance(api_key, api_secret)

    # 3. Check Env Vars (Admin)
    print("\n👑 Checking Admin Env Vars...")
    ak = os.getenv('BINANCE_API_KEY') or os.getenv('BINANCE_KEY')
    ask = os.getenv('BINANCE_SECRET') or os.getenv('BINANCE_API_SECRET')
    
    if ak and ask:
        check_balance(ak, ask)
    else:
        print("   ⚠️ No Admin Keys in Env.")

def check_balance(api_key, api_secret):
    try:
        client = Client(api_key, api_secret)
        
        # A. Futures Account
        print("   👉 futures_account()...")
        acc = client.futures_account()
        
        print(f"      availableBalance: {acc.get('availableBalance', 'MISSING')}")
        print(f"      totalMarginBalance: {acc.get('totalMarginBalance', 'MISSING')}")
        
        usdt_asset = next((a for a in acc.get('assets', []) if a['asset'] == 'USDT'), None)
        if usdt_asset:
            print(f"      [Asset USDT] walletBalance: {usdt_asset.get('walletBalance')}")
            print(f"      [Asset USDT] availableBalance: {usdt_asset.get('availableBalance')}")
            
        # B. Futures Balance list
        print("   👉 futures_account_balance()...")
        bal_list = client.futures_account_balance()
        usdt_bal_entry = next((b for b in bal_list if b['asset'] == 'USDT'), None)
        if usdt_bal_entry:
                print(f"      [Balance Endpoint] USDT Balance: {usdt_bal_entry.get('balance')}")
                print(f"      [Balance Endpoint] USDT Available: {usdt_bal_entry.get('availableBalance')}")
        else:
                print("      ⚠️ No USDT found in account_balance.")
                
    except Exception as e:
        print(f"   ❌ Error: {e}")

if __name__ == "__main__":
    debug_wallet()
