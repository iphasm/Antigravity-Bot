import asyncio
from ..strategies.factory import StrategyFactory
from ..risk.manager import RiskManager
from ..data.stream import MarketStream

class QuantumEngine:
    """
    Main Orchestrator for Antigravity Quantum.
    """
    def __init__(self):
        self.risk_guardian = RiskManager()
        self.market_stream = MarketStream('binance')
        self.running = False
        # Only testing a few assets for prototype to avoid rate limits
        self.assets = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'ADAUSDT', 'LTCUSDT', 'LINKUSDT', 'DOGEUSDT', 'AVAXUSDT', 'ZECUSDT', 'SUIUSDT'] 
        
    async def initialize(self):
        print("🌌 QuantumEngine: Initializing Subsystems...")
        await self.market_stream.initialize()
        
        # Simulating Async Config / DB Load
        await asyncio.sleep(0.5)
        print("✅ Risk Manager: Online")
        print("✅ Strategy Factory: Online")

    async def core_loop(self):
        """Main Decision Loop"""
        print("🚀 Quantum Core Loop Started.")
        while self.running:
            for asset in self.assets:
                print(f"🔍 Scanning {asset}...")
                
                # 1. Fetch Data (Real)
                market_data = await self.market_stream.get_candles(asset)
                if market_data['dataframe'].empty:
                    continue

                # 2. Get Dynamic Strategy
                # In real version, we calculate volatility from market_data to pick strategy
                volatility = 0.5 
                strategy = StrategyFactory.get_strategy(asset.replace('USDT',''), volatility)
                
                # 3. Analyze (Async)
                signal = await strategy.analyze(market_data)
                
                if signal:
                    print(f"💡 SIGNAL: {signal.action} on {asset} ({strategy.name}) | Conf: {signal.confidence:.2f}")
                    # 4. Risk Check
                    # approved = await self.risk_guardian.check_trade_approval(signal, exposure)
                
            await asyncio.sleep(10) # 10s wait

    async def run(self):
        self.running = True
        await self.initialize()
        
        # Concurrent Execution
        # In this Rest-Polling model, core_loop does the fetching.
        # IF we had websockets, we'd run them in parallel.
        await self.core_loop()

    async def stop(self):
        self.running = False
        print("🛑 Engine Stopping...")
        await self.market_stream.close()
