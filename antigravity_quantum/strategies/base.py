import abc
from dataclasses import dataclass
from typing import Dict, Any, Optional

@dataclass
class Signal:
    symbol: str
    action: str  # BUY, SELL, HOLD, EXIT
    confidence: float  # 0.0 to 1.0
    price: float
    metadata: Dict[str, Any]

class IStrategy(abc.ABC):
    """
    Interface for all Trading Strategies.
    """
    
    @abc.abstractmethod
    async def analyze(self, market_data: Dict[str, Any]) -> Signal:
        """
        Analyzes market data and returns a trading signal.
        """
        pass

    @abc.abstractmethod
    def calculate_entry_params(self, signal: Signal, wallet_balance: float) -> Dict[str, Any]:
        """
        Calculates position size, leverage, and stop-loss based on strategy logic.
        """
        pass
    
    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Strategy Name"""
        pass
