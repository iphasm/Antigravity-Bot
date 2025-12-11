from typing import Dict, Any
from .base import IStrategy, Signal

class GridTradingStrategy(IStrategy):
    """
    Grid Strategy for Sideways/Accumulation Assets (ADA).
    Logic: Divides range into N levels. Buy Low, Sell High.
    """
    
    def __init__(self, grid_levels=10, grid_spacing_pct=0.01):
        self.grid_levels = grid_levels
        self.spacing = grid_spacing_pct
        self.base_price = None

    @property
    def name(self) -> str:
        return "GridMaster (ADA)"

    async def analyze(self, market_data: Dict[str, Any]) -> Signal:
        """
        Grid logic doesn't output a single signal per se, 
        but usually checks if price hit a grid line.
        For this architecture, we signal ENTRY if we are at bottom of grid.
        """
        df = market_data.get('dataframe')
        if df is None or df.empty: return None
        
        current_price = df.iloc[-1]['close']
        
        # Initialize Grid Center if needed
        if self.base_price is None:
            self.base_price = df.iloc[-1]['ema_200'] # Anchor to EMA200
            
        # Calc Deviation
        dev = (current_price - self.base_price) / self.base_price
        
        signal_type = "HOLD"
        confidence = 0.0
        
        # Simple Mean Reversion / Grid Logic
        if dev < -self.spacing * 2: # price drops 2 grids below center
            signal_type = "BUY"
            confidence = 0.8
        elif dev > self.spacing * 2: # price pops 2 grids above
            signal_type = "SELL"
            confidence = 0.8
            
        return Signal(
            symbol="ADA",
            action=signal_type,
            confidence=confidence,
            price=current_price,
            metadata={"grid_dev": dev}
        )

    def calculate_entry_params(self, signal: Signal, wallet_balance: float) -> Dict[str, Any]:
        """
        Grid trades are small, frequent, no tight SL (usually uses cross margin or wide SL).
        """
        return {
            "leverage": 2, # Low leverage for Grid
            "size_pct": 0.02, # Small position (2%)
            "stop_loss_price": signal.price * 0.85, # Wide SL (15%) for safety
            "take_profit_price": signal.price * 1.02 # Quick TP (2%)
        }
