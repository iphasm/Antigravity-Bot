import os
import yfinance as yf
import pandas as pd
from binance.client import Client

# Initialize Binance Client
# Use environment variables if present, otherwise default to public mode
api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_SECRET')

# Proxy Configuration
proxy_url = os.getenv('PROXY_URL')
request_params = {'proxies': {'https': proxy_url}} if proxy_url else None

client = None
try:
    if api_key and api_secret:
        client = Client(api_key, api_secret, tld='com', requests_params=request_params)
        proxy_msg = f" [Proxy: {'Enabled' if proxy_url else 'Disabled'}]"
        print(f"✅ Binance Client (Authenticated) initialized for data [International API]{proxy_msg}.")
    else:
        client = Client(tld='com', requests_params=request_params)
        proxy_msg = f" [Proxy: {'Enabled' if proxy_url else 'Disabled'}]"
        print(f"⚠️ Binance Client (Public Only) initialized [International API]{proxy_msg}. Trading will fail, but data fetching works.")
except Exception as e:
    print(f"❌ Warning: Binance Client init failed in fetcher: {e}")
    # Fallback to public
    try:
        client = Client(tld='com', requests_params=request_params)
    except:
        pass

def get_market_data(symbol: str, timeframe: str = '15m', limit: int = 100) -> pd.DataFrame:
    """
    Fetches market data from Binance (Crypto) or YFinance (Stocks).
    
    Args:
        symbol: Ticker symbol (e.g., 'BTCUSDT', 'MSFT').
        timeframe: Candle timeframe (default '15m').
        limit: Number of candles to return (default 100).
        
    Returns:
        pd.DataFrame: Columns ['timestamp', 'open', 'high', 'low', 'close', 'volume'].
    """
    
    expected_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
    
    try:
        # --- CRYPTO (Binance) ---
        if 'USDT' in symbol.upper() or 'BUSD' in symbol.upper():
            print(f"DEBUG: Fetching crypto for {symbol}...")
            if not client:
                print("DEBUG: Client is None!")
                return pd.DataFrame(columns=expected_cols)
                
            # Map timeframe
            # Binance uses: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h, 6h, 8h, 12h, 1d, 3d, 1w, 1M
            # Just pass directly if valid
            
            # Fetch Klines
            try:
                print(f"DEBUG: Attempting client.get_klines for {symbol}")
                klines = client.get_klines(symbol=symbol, interval=timeframe, limit=limit)
                print(f"DEBUG: Auth fetch result: {len(klines) if klines else 'None/Empty'}")
            except Exception as e:
                print(f"⚠️ Authenticated fetch failed for {symbol} ({e}). Retrying with Public Client...")
                try:
                    # Reuse proxy config (request_params is globally defined above)
                    public_client = Client(tld='com', requests_params=request_params)
                    klines = public_client.get_klines(symbol=symbol, interval=timeframe, limit=limit)
                    print(f"DEBUG: Public fetch result: {len(klines) if klines else 'None/Empty'}")
                except Exception as e2:
                     print(f"❌ Public fetch also failed for {symbol}: {e2}")
                     return pd.DataFrame(columns=expected_cols)
            
            if not klines:
                print(f"DEBUG: klines is empty for {symbol}")
                return pd.DataFrame(columns=expected_cols)
            
            # Binance Klines: 
            # [
            #   [1499040000000,      // Open time
            #    "0.01634790",       // Open
            #    "0.80000000",       // High
            #    "0.01575800",       // Low
            #    "0.01577100",       // Close
            #    "148976.11427815",  // Volume
            #    1499644799999,      // Close time
            #    ...
            #   ]
            # ]
            
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume', 
                'close_time', 'quote_asset_volume', 'number_of_trades', 
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            
            # Clean up
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            
            # Types
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
                
            return df

        # --- STOCK (YFINANCE) ---
        else:
            ticker = yf.Ticker(symbol)
            
            # Map timeframe/limit
            fetch_period = "1mo"
            if timeframe in ['1m', '2m', '5m']:
                fetch_period = "5d"
                
            df = ticker.history(interval=timeframe, period=fetch_period)
            
            if df.empty:
                return pd.DataFrame(columns=expected_cols)
            
            df = df.reset_index()
            
            rename_map = {
                'Date': 'timestamp', 
                'Datetime': 'timestamp',
                'Open': 'open', 
                'High': 'high', 
                'Low': 'low', 
                'Close': 'close', 
                'Volume': 'volume'
            }
            df = df.rename(columns=rename_map)
            
            # Ensure columns exist
            for col in expected_cols:
                if col not in df.columns:
                    df[col] = 0.0
            
            df = df[expected_cols]
            df = df.sort_values('timestamp', ascending=True)
            df = df.reset_index(drop=True)
            
            if len(df) > limit:
                df = df.tail(limit).reset_index(drop=True)
                
            return df

    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return pd.DataFrame(columns=expected_cols)
