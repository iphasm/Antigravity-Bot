from typing import Dict, Any
from .base import IStrategy, Signal

class ScalpingStrategy(IStrategy):
    @property
    def name(self) -> str:
        return "Scalping (High Vol)"

    async def analyze(self, market_data: Dict[str, Any]) -> Signal:
        """
        Scalping Strategy for High Volatility.
        Logic: Quick entries on Momentum Breakouts (RSI crossing 50/60) + Volume Spike.
        """
        df = market_data.get('dataframe')
        if df is None or df.empty: return None
        
        # Latest Candles
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Indicators (Assuming they are computed in Stream)
        rsi = last.get('rsi', 50)
        adx = last.get('adx', 0)
        close = last['close']
        ema_200 = last.get('ema_200', close) # Fallback to close if missing
        
        signal_type = "HOLD"
        confidence = 0.0
        
        # MOMENTUM LONG
        # RSI crosses above 55, ADX > 25 (Trend Strength) 
        # FILTER: Price > EMA 200 (Only with trend)
        if rsi > 55 and last['rsi'] > prev['rsi'] and adx > 25 and close > ema_200:
            signal_type = "BUY"
            confidence = 0.7 + (min(adx, 50)/200) # Boost conf with ADX
            
        # MOMENTUM SHORT
        # RSI crosses below 45, ADX > 25
        # FILTER: Price < EMA 200 (Only with trend)
        elif rsi < 45 and last['rsi'] < prev['rsi'] and adx > 25 and close < ema_200:
            signal_type = "SELL"
            confidence = 0.7 + (min(adx, 50)/200)
            
        if signal_type == "HOLD":
            return None
            
        return Signal(
            symbol="UNKNOWN", # Engine sets this
            action=signal_type,
            confidence=confidence,
            price=last['close'],
            metadata={"strategy": "Scalping", "rsi": rsi, "adx": adx}
        )

    def calculate_entry_params(self, signal: Signal, wallet_balance: float) -> Dict[str, Any]:
        """
        Scalping: High Leverage, Tight Stops, Quick TP.
        """
        return {
            "leverage": 10, 
            "size_pct": 0.05, # 5% per trade
            "stop_loss_price": signal.price * (0.99 if signal.action == "BUY" else 1.01), # 1% SL
            "take_profit_price": signal.price * (1.015 if signal.action == "BUY" else 0.985) # 1.5% TP
        }
