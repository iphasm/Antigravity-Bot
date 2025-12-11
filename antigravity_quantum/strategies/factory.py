from .base import IStrategy
from .trend import TrendFollowingStrategy
from .grid import GridTradingStrategy
from .mean_reversion import MeanReversionStrategy
from .scalping import ScalpingStrategy

class StrategyFactory:
    """
    Dynamic Factory to assign strategies based on asset profile.
    """
    
    @staticmethod
    def get_strategy(symbol: str, volatility_index: float) -> IStrategy:
        """
        Assigns the optimal strategy.
        Rules:
        - BTC -> Trend Following (Dominance)
        - ADA -> Grid (Accumulation)
        - High Vol -> Scalping
        - Default -> Mean Reversion
        """
        if symbol == 'BTC':
            return TrendFollowingStrategy()
        
        if symbol == 'ADA':
            return GridTradingStrategy()
            
        if volatility_index > 0.8:
            return ScalpingStrategy()
            
        return MeanReversionStrategy()
