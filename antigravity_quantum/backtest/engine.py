import asyncio
import pandas as pd
from typing import Dict, List
from ..strategies.factory import StrategyFactory
from ..data.stream import MarketStream

class BacktestEngine:
    def __init__(self, assets: List[str], initial_capital: float = 1000.0, days: int = 30):
        self.assets = assets
        self.initial_capital = initial_capital
        self.days = days
        self.market_stream = MarketStream()
        
    async def run(self, strategy_override: IStrategy = None):
        print(f"\n🚀 STARTING BACKTEST SIMULATION (Pilot Mode)")
        print(f"🎯 Assets: {self.assets}")
        print(f"💰 Initial Capital: ${self.initial_capital:,.2f} per asset")
        print(f"🗓️  Period: Last {self.days} Days\n{'='*50}")
        
        await self.market_stream.initialize()
        
        results = {}
        
        for asset in self.assets:
            print(f"\n🔍 Analyzing {asset}...")
            
            # 1. Fetch History
            df = await self.market_stream.get_historical_candles(asset, days=self.days)
            if df.empty:
                print(f"❌ No data for {asset}")
                continue
                
            # 2. Setup Simulation State
            balance = self.initial_capital
            position = None # {'entry': float, 'size': float}
            trades_log = []
            
            if strategy_override:
                strategy = strategy_override
            else:
                strategy = StrategyFactory.get_strategy(asset.replace('USDT',''), volatility_index=0.5)
            print(f"⚙️  Strategy: {strategy.name}")
            
            # 3. Iterate (Skip warmup)
            warmup = 50
            for i in range(warmup, len(df)):
                # Create window for strategy
                msg_df = df.iloc[:i+1] # Strategy analyzes full df up to now
                # In a real efficient backtester we'd optimize this slicing, but for 3000 rows it's fine.
                
                # Mock current candle
                current_price = df.iloc[i]['close']
                timestamp = df.iloc[i]['timestamp']
                
                # Analyze
                # Since strategy.analyze expects specific format
                market_data = {
                    "symbol": asset,
                    "timeframe": "15m",
                    "dataframe": msg_df
                }
                
                signal = await strategy.analyze(market_data)
                
                if not signal:
                    continue
                    
                # Execution Logic (Simple Spot)
                fee = 0.001 # 0.1% Binance Spot Fee
                
                # BUY CONDITION
                if signal.action == "BUY" and position is None:
                    entry_price = current_price
                    size = (balance * 0.99) / entry_price # 99% usage to cover fees safe
                    cost = size * entry_price
                    balance -= cost
                    
                    position = {
                        'entry': entry_price,
                        'size': size,
                        'time': timestamp
                    }
                    trades_log.append({
                        'type': 'BUY',
                        'price': entry_price,
                        'time': timestamp,
                        'balance': balance
                    })
                    
                # SELL CONDITION
                elif (signal.action == "SELL" or signal.action == "EXIT") and position is not None:
                    exit_price = current_price
                    revenue = position['size'] * exit_price * (1 - fee)
                    
                    pnl = revenue - (position['size'] * position['entry'])
                    pnl_pct = (pnl / (position['size'] * position['entry'])) * 100
                    
                    balance += revenue
                    position = None
                    
                    trades_log.append({
                        'type': 'SELL',
                        'price': exit_price,
                        'time': timestamp,
                        'balance': balance,
                        'pnl': pnl,
                        'pnl_pct': pnl_pct
                    })

            # Check open position at end
            if position:
                # Mark to market
                current_val = position['size'] * df.iloc[-1]['close']
                balance += current_val
            
            roi = ((balance - self.initial_capital) / self.initial_capital) * 100
            
            results[asset] = {
                'final_balance': balance,
                'roi': roi,
                'trades': len(trades_log),
                'history': trades_log
            }
            
            print(f"🏁 Result: ${balance:,.2f} ({roi:+.2f}%) | Trades: {len(trades_log)}")

        await self.market_stream.close()
        return results
