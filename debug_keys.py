
import os
import sys
from dotenv import load_dotenv
from binance.client import Client

# Load Env
load_dotenv()

# Dictionary of potential key names to try
KEY_NAMES = ['BINANCE_API_KEY', 'BINANCE_KEY', 'API_KEY']
SECRET_NAMES = ['BINANCE_SECRET', 'BINANCE_API_SECRET', 'SECRET_KEY']

found_key = None
found_secret = None

print("--- ENVIRONMENT VARIABLE SCAN ---")
for k in KEY_NAMES:
    val = os.getenv(k)
    if val:
        print(f"✅ FOUND {k}: {val[:4]}...{val[-4:]}")
        found_key = val
        break
    else:
        print(f"❌ {k}: Not set")

for s in SECRET_NAMES:
    val = os.getenv(s)
    if val:
        print(f"✅ FOUND {s}: {val[:4]}...{val[-4:]}")
        found_secret = val
        break
    else:
        print(f"❌ {s}: Not set")

proxy = os.getenv('PROXY_URL')
print(f"🌍 PROXY: {proxy}")

if not found_key or not found_secret:
    print("❌ CREDENTIALS MISSING. Cannot proceed.")
    sys.exit()

print("--- CONNECTING TO BINANCE ---")
try:
    client = Client(
        found_key, 
        found_secret, 
        requests_params={'proxies': {'https': proxy}} if proxy else None
    )
    print("✅ Client Created.")
except Exception as e:
    print(f"❌ Client Init Error: {e}")
    sys.exit()

print("\n--- 1. TESTING EARN (Flexible) ---")
try:
    # Try Simple Earn Flexible
    flex_pos = client.get_simple_earn_flexible_position()
    print(f"Flexible Positions Found: {len(flex_pos)}")
    for p in flex_pos:
        print(f" - {p['asset']}: {p['totalAmount']}")
except Exception as e:
    print(f"❌ Error Simple Earn Flexible: {e}")

try:
    # Try User Asset (Universal)
    # This often reveals assets in Earn/Savings/Funding that aren't in Spot limits
    print("\n--- 1b. TESTING USER ASSET (Universal) ---")
    assets = client.get_user_asset()
    for a in assets:
        if float(a['free']) > 0 or float(a['locked']) > 0 or float(a['freeze']) > 0:
            print(f" - {a['asset']}: Free={a['free']}, Locked={a['locked']}, Freeze={a['freeze']}")
except Exception as e:
    print(f"❌ Error User Asset: {e}")


print("\n--- 3. TESTING PNL (Futures) ---")
try:
    # Check Income History for REALIZED_PNL
    income = client.futures_income_history(incomeType='REALIZED_PNL', limit=10)
    print(f"PnL Entries Found: {len(income)}")
    for i in income:
        print(f" - {i['symbol']} ({i['time']}): {i['income']}")
        
    # Also check transaction history just in case
    print("\n--- 3b. TESTING INCOME (Generic) ---")
    income_gen = client.futures_income_history(limit=5)
    for i in income_gen:
         print(f" - {i['incomeType']}: {i['income']}")

except Exception as e:
    print(f"❌ Error PnL: {e}")
