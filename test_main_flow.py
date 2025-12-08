"""
Quick diagnostic script to test the exact flow from main.py
"""
from data.fetcher import get_market_data
from strategies.analyzer import analyze_market

WATCHLIST = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT']

print("=== SIMULATING MAIN.PY FLOW ===\n")

for asset in WATCHLIST:
    try:
        print(f"\n--- Testing {asset} ---")
        # Same call as in main.py line 162
        df = get_market_data(asset, timeframe='15m', limit=100)
        
        if df.empty:
            print(f"❌ {asset}: No data (DataFrame is empty)")
            continue
        
        print(f"✅ {asset}: Got {len(df)} rows")
        
        # Test analyze_market
        buy_signal, metrics = analyze_market(df)
        price = metrics.get('close', 0)
        rsi = metrics.get('rsi', 0)
        
        print(f"   Price: ${price:.2f}")
        print(f"   RSI: {rsi:.2f}")
        print(f"   Buy Signal: {buy_signal}")
        
    except Exception as e:
        print(f"❌ Error processing {asset}: {e}")
        import traceback
        traceback.print_exc()

print("\n=== DIAGNOSTIC COMPLETE ===")
