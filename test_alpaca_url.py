
from alpaca.trading.client import TradingClient
import os

# Mock environment
ak = "PK_MOCK"
ask = "SK_MOCK"
# URL with /v2 suffix as requested by user
base_url_v2 = "https://paper-api.alpaca.markets/v2" 

print(f"Testing URL construction with base: {base_url_v2}")

try:
    client = TradingClient(ak, ask, url_override=base_url_v2)
    
    # We want to see what URL it calls. 
    # In alpaca-py, client._get_path method or similar constructs it.
    # Or we can inspect client._base_url
    
    print(f"Client Base URL: {client._base_url}")
    
    # Let's see how it constructs an order URL
    # Usually it appends /v2/orders. 
    # If base already has /v2, does it double it?
    
    # We can try to rely on internal method if public one isn't available for inspection.
    # Looking at alpaca-py source (mental check), it usually appends version if using common methods, 
    # BUT TradingClient often assumes base_url is the ROOT. 
    
    # Let's inspect a constructed URL for 'get_account'
    # It calls GET /v2/account
    
    # We can mock the requester or just print the concatenation logic if we knew it.
    # Since we can't easily see source, we will run this and if it prints https://.../v2, we know it accepted it.
    # The real test is if it doubles it.
    
    # Let's try to trigger a request and fail but capture URL if possible? No easy way without mock.
    
    # Alternative: Check if we can strip /v2 if the library adds it automatically.
    # Standard Alpaca client adds /v2 automatically.
    
    if client._base_url.endswith('/v2'):
         print("⚠️ Client base URL ends with /v2. Potential double-suffix risk if library appends /v2.")
    else:
         print("✅ Client base URL looks clean (no /v2 suffix stored).")

except Exception as e:
    print(f"Error: {e}")
