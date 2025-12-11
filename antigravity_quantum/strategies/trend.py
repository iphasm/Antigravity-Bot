import pandas as pd
from typing import Dict, Any
from .base import IStrategy, Signal

class TrendFollowingStrategy(IStrategy):
    """
    Classic Trend Following for Dominant Assets (BTC).
    Logic: EMA Crossover (20/50) + ADX > 25 Filter.
    """
    
    @property
    def name(self) -> str:
        return "TrendFollowing (BTC)"

    async def analyze(self, market_data: Dict[str, Any]) -> Signal:
        """
        Expects market_data to contain a DataFrame with 'close', 'high', 'low'.
        """
        df = market_data.get('dataframe')
        if df is None or df.empty:
            return None

        # 1. Indicators (Simplified for Proto)
        # Assuming df has calculated indicators or we calculate here
        # For prototype, we check the last row
        last_row = df.iloc[-1]
        
        # Logic: EMA 20 > EMA 50 AND ADX > 25
        ema_short = last_row.get('ema_20', 0)
        ema_long = last_row.get('ema_50', 0)
        adx = last_row.get('adx', 0)
        price = last_row.get('close', 0)
        
        signal_type = "HOLD"
        confidence = 0.0
        
        if ema_short > ema_long and adx > 25:
            signal_type = "BUY"
            confidence = min(adx / 50, 1.0) # Normalize confidence
            
        elif ema_short < ema_long and adx > 25:
            signal_type = "SELL"
            confidence = min(adx / 50, 1.0)
            
        return Signal(
            symbol="BTC",
            action=signal_type,
            confidence=confidence,
            price=price,
            metadata={"adx": adx, "ema_diff": ema_short - ema_long}
        )

    def calculate_entry_params(self, signal: Signal, wallet_balance: float) -> Dict[str, Any]:
        """
        Trend strategies use wider stops (ATR * 2) and try to ride the wave.
        """
        atr = signal.metadata.get('atr', 100) # Fallback
        
        return {
            "leverage": 5, # BTC allows higher lev
            "size_pct": 0.10, # 10% of equity
            "stop_loss_price": signal.price - (atr * 2) if signal.action == "BUY" else signal.price + (atr * 2),
            "take_profit_price": signal.price + (atr * 4) if signal.action == "BUY" else signal.price - (atr * 4)
        }
