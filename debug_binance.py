import os
from binance.client import Client

def test_fetch():
    print("--- DEBUG BINANCE FETCH ---")
    
    # Try Public
    print("# Attempting Public Client Init...")
    try:
        client = Client()
        print("✅ Client init successful (Public)")
        
        symbol = "BTCUSDT"
        print(f"# Fetching klines for {symbol}...")
        klines = client.get_klines(symbol=symbol, interval='15m', limit=5)
        
        if klines:
            print(f"✅ Success! Received {len(klines)} candles.")
            print(f"Sample: {klines[0]}")
        else:
            print("❌ Success response but EMPTY list returned.")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_fetch()
