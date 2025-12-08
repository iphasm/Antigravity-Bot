from data.fetcher import get_market_data

def run_debug():
    print("--- STARTING DEBUG RUNNER ---")
    symbol = "BTCUSDT"
    print(f"Calling get_market_data('{symbol}', ...)")
    
    df = get_market_data(symbol, timeframe='15m', limit=100)
    
    print("\n--- RESULT ---")
    if df.empty:
        print(f"❌ DataFrame is EMPTY.")
    else:
        print(f"✅ Data received. Rows: {len(df)}")
        print(df.head(2))
        print(df.tail(2))

if __name__ == "__main__":
    run_debug()
