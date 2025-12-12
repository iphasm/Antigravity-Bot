from .base import IStrategy
from .trend import TrendFollowingStrategy
from .grid import GridTradingStrategy
from .mean_reversion import MeanReversionStrategy
from .scalping import ScalpingStrategy
from ..config import ENABLED_STRATEGIES, GRID_WHITELIST, SCALPING_WHITELIST

class StrategyFactory:
    """
    Dynamic Factory to assign strategies based on asset profile and Global Config.
    """
    
    @staticmethod
    def get_strategy(symbol: str, volatility_index: float) -> IStrategy:
        """
        Assigns the optimal strategy based on flags and whitelist.
        """
        # 1. GRID STRATEGY (Sideways/Accumulation)
        if ENABLED_STRATEGIES.get('GRID', False):
            if symbol in GRID_WHITELIST:
                return GridTradingStrategy()
        
        # 2. SCALPING STRATEGY (High Volatility)
        if ENABLED_STRATEGIES.get('SCALPING', False):
            if symbol in SCALPING_WHITELIST and volatility_index > 0.6:
                return ScalpingStrategy()
        
        # 3. TREND FOLLOWING (Only BTC/Major dominance)
        if symbol == 'BTC':
            return TrendFollowingStrategy()
            
        # 4. DEFAULT: Mean Reversion (Safest)
        return MeanReversionStrategy()
