import asyncio
import sys
import os

# Ensure root is in path
sys.path.append(os.getcwd())

from antigravity_quantum.backtest.engine import BacktestEngine
from antigravity_quantum.strategies.scalping import ScalpingStrategy
from antigravity_quantum.strategies.grid import GridTradingStrategy
from antigravity_quantum.strategies.mean_reversion import MeanReversionStrategy

async def run_simulation(name, strategy_obj, assets, days, capital):
    """Helper to run a single sim"""
    print(f"\n\n🎰 **RUNNING SIMULATION: {name.upper()}**")
    print("〰️" * 40)
    
    engine = BacktestEngine(assets, initial_capital=capital, days=days)
    results = await engine.run(strategy_override=strategy_obj)
    
    total_pnl = 0
    total_balance = 0
    total_start = len(assets) * capital
    
    print(f"\n📊 **RESULTS FOR {name.upper()}**")
    for asset, data in results.items():
        symbol = asset.replace('USDT', '')
        balance = data['final_balance']
        roi = data['roi']
        trades = data['trades']
        pnl = balance - capital
        
        total_pnl += pnl
        total_balance += balance
        
        icon = "🟢" if roi > 0 else "🔴"
        print(f"   {icon} {symbol}: ${balance:,.0f} ({roi:+.1f}%) | {trades} Trades")

    total_roi = ((total_balance - total_start) / total_start) * 100
    print(f"\n🏆 **TOTAL {name}: ROI {total_roi:+.2f}% | PnL ${total_pnl:,.0f}**")
    return total_roi

async def main():
    try:
        assets = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 
                  'ADAUSDT', 'LTCUSDT', 'LINKUSDT', 'DOGEUSDT', 'AVAXUSDT', 
                  'ZECUSDT', 'SUIUSDT']
        
        # Total Capital for Account = 1000 USDT
        TOTAL_CAPITAL = 1000.0
        capital_per_asset = TOTAL_CAPITAL / len(assets) 
        
        days = 90
        
        # 1. SCALPING (Momentum)
        roi_scalp = await run_simulation("Scalping (Momentum)", ScalpingStrategy(), assets, days, capital_per_asset)
        
        # 2. GRID (Accumulation)
        roi_grid = await run_simulation("Grid (Accumulation)", GridTradingStrategy(), assets, days, capital_per_asset)
        
        # 3. MEAN REVERSION (Baseline)
        roi_mean = await run_simulation("Mean Reversion (Baseline)", MeanReversionStrategy(), assets, days, capital_per_asset)
        
        print("\n\n🏁 **COMPARATIVE SUMMARY**")
        print("〰️" * 30)
        print(f"1️⃣ Scalping:       {roi_scalp:+.2f}%")
        print(f"2️⃣ Mean Reversion: {roi_mean:+.2f}%")
        print(f"3️⃣ Grid Trading:   {roi_grid:+.2f}%")
        print("〰️" * 30)

    except Exception as e:
        print(f"❌ CRITICAL ERROR IN BACKTEST: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
