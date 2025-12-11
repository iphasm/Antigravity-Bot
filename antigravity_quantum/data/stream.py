import ccxt.async_support as ccxt
import pandas as pd
import asyncio
from typing import Dict, Any, List

class MarketStream:
    """
    Async Market Data Provider.
    Currently uses REST Polling via CCXT (Async).
    Can be upgraded to WebSockets (CCXT Pro) later.
    """
    def __init__(self, exchange_id='binance'):
        self.exchange_id = exchange_id
        self.exchange = getattr(ccxt, exchange_id)()
        self.tf_map = {
            'BTC': '15m',  # Fast trend
            'ETH': '15m',
            'SOL': '5m',   # Scalping
            'ADA': '1h',   # Grid/Swing
            'default': '15m'
        }

    async def initialize(self):
        """Load markets"""
        try:
            print(f"🔌 Connecting to {self.exchange_id}...")
            await self.exchange.load_markets()
            print(f"✅ Connected to {self.exchange_id} (Async).")
        except Exception as e:
            print(f"❌ Connection Failed: {e}")

    async def get_candles(self, symbol: str, limit: int = 100) -> Dict[str, Any]:
        """
        Fetches OHLCV data and returns a formatted dict ready for Strategy.analyze()
        """
        # 1. Resolve Timeframe based on asset config (Dynamic)
        timeframe = self.tf_map.get(symbol.split('USDT')[0], self.tf_map['default'])
        
        try:
            # 2. Fetch (Async)
            # symbol needs to be compatible with ecxchange (e.g. BTC/USDT)
            # internal we might use BTCUSDT, ccxt needs BTC/USDT usually
            formatted_symbol = symbol.replace('USDT', '/USDT') if 'USDT' in symbol and '/' not in symbol else symbol
            
            ohlcv = await self.exchange.fetch_ohlcv(formatted_symbol, timeframe, limit=limit)
            
            # 3. Parse to DataFrame
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            
            # 4. Add Basic Indicators (Lightweight)
            # Ideally this moves to a 'Technicals' module, but keeping here for speed
            df['ema_20'] = df['close'].ewm(span=20).mean()
            df['ema_50'] = df['close'].ewm(span=50).mean()
            df['ema_200'] = df['close'].ewm(span=200).mean()
            
            # ADX placeholder (Requires complex calc, mocking for prototype)
            # In production, use pandas_ta or ta-lib
            df['adx'] = 30.0 # Mock to allow Trend Strategy to trigger
            
            return {
                "symbol": symbol,
                "timeframe": timeframe,
                "dataframe": df
            }
            
        except Exception as e:
            print(f"⚠️ Data Fetch Error ({symbol}): {e}")
            return {"dataframe": pd.DataFrame()} # Empty DF

    async def close(self):
        await self.exchange.close()
