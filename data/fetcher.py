import os
import yfinance as yf
import pandas as pd
from binance.client import Client

# Initialize Binance Client
# Use environment variables if present, otherwise default to public mode
# --- BINANCE SETUP ---
api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_SECRET')

# --- ALPACA SETUP ---
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from datetime import datetime, timedelta

alpaca_api_key = os.getenv('APCA_API_KEY_ID')
alpaca_secret_key = os.getenv('APCA_API_SECRET_KEY')
alpaca_data_client = None

try:
    if alpaca_api_key and alpaca_secret_key:
        alpaca_data_client = StockHistoricalDataClient(alpaca_api_key, alpaca_secret_key)
        print("✅ Alpaca Data Client initialized.")
    else:
        print("⚠️ Alpaca Keys missing. Stocks will use YFinance (Delayed/Unofficial).")
except Exception as e:
    print(f"❌ Warning: Alpaca Client init failed: {e}")

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

# --- ASSET CONFIG (Needed for Resolve Symbol) ---
# NOTE:Ideally this should come from config.py to avoid duplication,
# but for now we inline it to resolve the immediate 'resolve_symbol' dependency.
ASSET_GROUPS = {
    'CRYPTO': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'ADAUSDT', 'LTCUSDT', 'LINKUSDT', 'DOGEUSDT', 'AVAXUSDT', 'ZECUSDT', 'SUIUSDT'],
    'STOCKS': ['TSLA', 'NVDA', 'MSFT', 'AAPL', 'AMD'],
    'COMMODITY': ['GLD', 'USO', 'SLV', 'CPER', 'UNG'] 
}
TICKER_MAP = {
    'BTCUSDT': 'Bitcoin', 'ETHUSDT': 'Ethereum', 'SOLUSDT': 'Solana', 'BNBUSDT': 'Binance Coin',
    'XRPUSDT': 'Ripple', 'ADAUSDT': 'Cardano', 'LTCUSDT': 'Litecoin', 'LINKUSDT': 'Chainlink',
    'DOGEUSDT': 'Dogecoin', 'AVAXUSDT': 'Avalanche', 'ZECUSDT': 'Zcash', 'SUIUSDT': 'Sui',
    'TSLA': 'Tesla', 'NVDA': 'NVIDIA', 'MSFT': 'Microsoft', 'AAPL': 'Apple', 'AMD': 'AMD',
    'GLD': 'ORO', 'USO': 'PETROLEO', 'SLV': 'PLATA', 'CPER': 'COBRE', 'UNG': 'GAS NATURAL'
}

def resolve_symbol(text):
    """Limpia y estandariza el símbolo (input). Agrega 'USDT' automáticamente."""
    s = text.strip().upper().replace('/', '').replace('-', '').replace('_', '')
    
    # 1. Exact Match Check
    known_assets = []
    for g in ASSET_GROUPS.values():
        known_assets.extend(g)
    
    if s in known_assets or s in TICKER_MAP:
        return s
        
    # 2. Reverse Lookup
    for ticker, name in TICKER_MAP.items():
        if s == name.upper():
            return ticker
            
    # 3. Try Appending USDT
    s_usdt = s + "USDT"
    if s_usdt in ASSET_GROUPS.get('CRYPTO', []) or s_usdt in TICKER_MAP:
        return s_usdt
        
    return s

def get_market_data(symbol: str, timeframe: str = '15m', limit: int = 100) -> pd.DataFrame:
    """
    Fetches market data from Binance (Crypto) or YFinance (Stocks).
    """
    expected_cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
    
    try:
        # --- ROUTING LOGIC ---
        is_crypto = 'USDT' in symbol.upper() or 'BUSD' in symbol.upper()
        # Explicit check for Stocks/Commodities to be safe
        if symbol in ASSET_GROUPS.get('STOCKS', []) or symbol in ASSET_GROUPS.get('COMMODITY', []):
            is_crypto = False

        # --- CRYPTO (Binance) ---
        if is_crypto:
            # print(f"DEBUG: Fetching crypto for {symbol}...") # Reduced noise
            if not client:
                return pd.DataFrame(columns=expected_cols)
                
            # Fetch Klines
            try:
                klines = client.get_klines(symbol=symbol, interval=timeframe, limit=limit)
            except Exception as e:
                print(f"⚠️ Authenticated fetch failed for {symbol} ({e}). Retrying with Public Client...")
                try:
                    public_client = Client(tld='com', requests_params=request_params)
                    klines = public_client.get_klines(symbol=symbol, interval=timeframe, limit=limit)
                except Exception as e2:
                     print(f"❌ Public fetch also failed for {symbol}: {e2}")
                     try:
                         yf_sym = symbol.replace('USDT', '-USD')
                         # print(f"⚠️ Binance blocked? Falling back to YFinance for {symbol} -> {yf_sym}")
                         import yfinance as yf
                         yf_period = "1mo"
                         if timeframe in ['1m', '5m', '15m']: yf_period = "5d"
                         df = yf.Ticker(yf_sym).history(interval=timeframe, period=yf_period)
                         if not df.empty:
                             df = df.reset_index()
                             rename_map = {'Date': 'timestamp', 'Datetime': 'timestamp', 'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'}
                             df = df.rename(columns=rename_map)
                             for c in expected_cols:
                                 if c not in df.columns: df[c] = 0.0
                             df = df[expected_cols]
                             if pd.api.types.is_datetime64_any_dtype(df['timestamp']) and df['timestamp'].dt.tz is not None:
                                 df['timestamp'] = df['timestamp'].dt.tz_convert(None)
                             return df
                     except Exception as ex_yf:
                         print(f"❌ YF Fallback failed: {ex_yf}")
                     return pd.DataFrame(columns=expected_cols)
            
            if klines is None or len(klines) == 0:
                return pd.DataFrame(columns=expected_cols)
            
            # Binance Klines to DF
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume', 
                'close_time', 'quote_asset_volume', 'number_of_trades', 
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']]
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
            return df

        # --- STOCK (ALPACA or YFINANCE) ---
        else:
            # 1. Try Alpaca First
            if alpaca_data_client:
                try:
                    alpaca_tf = TimeFrame(15, TimeFrameUnit.Minute) 
                    if timeframe == '1m': alpaca_tf = TimeFrame.Minute
                    elif timeframe == '5m': alpaca_tf = TimeFrame(5, TimeFrameUnit.Minute)
                    elif timeframe == '1h': alpaca_tf = TimeFrame.Hour
                    elif timeframe == '1d': alpaca_tf = TimeFrame.Day
                    
                    start_dt = datetime.utcnow() - timedelta(days=10) 
                    req = StockBarsRequest(symbol_or_symbols=symbol, timeframe=alpaca_tf, start=start_dt, limit=limit)
                    bars = alpaca_data_client.get_stock_bars(req)
                    
                    if not bars.df.empty:
                        df = bars.df.reset_index()
                        rename_map = {'timestamp': 'timestamp', 'open': 'open', 'high': 'high', 'low': 'low', 'close': 'close', 'volume': 'volume'}
                        for old, new in rename_map.items():
                             if old not in df.columns: df[new] = 0.0
                        df = df[list(rename_map.values())] 
                        if df['timestamp'].dt.tz is not None:
                             df['timestamp'] = df['timestamp'].dt.tz_convert(None)
                        return df
                except Exception as e:
                    pass # Fail silent, try YF

            # 2. Fallback to YFinance
            ticker = yf.Ticker(symbol)
            fetch_period = "1mo"
            if timeframe in ['1m', '2m', '5m']: fetch_period = "5d"
            df = ticker.history(interval=timeframe, period=fetch_period)
            if df.empty: return pd.DataFrame(columns=expected_cols)
            
            df = df.reset_index()
            rename_map = {'Date': 'timestamp', 'Datetime': 'timestamp', 'Open': 'open', 'High': 'high', 'Low': 'low', 'Close': 'close', 'Volume': 'volume'}
            df = df.rename(columns=rename_map)
            for col in expected_cols:
                if col not in df.columns: df[col] = 0.0
            
            df = df[expected_cols]
            df = df.sort_values('timestamp', ascending=True)
            df = df.reset_index(drop=True)
            if len(df) > limit:
                df = df.tail(limit).reset_index(drop=True)
            return df

    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
        return pd.DataFrame(columns=expected_cols)
