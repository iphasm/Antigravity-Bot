from typing import Dict, Any
from .base import IStrategy, Signal

class MeanReversionStrategy(IStrategy):
    @property
    def name(self) -> str:
        return "MeanReversion (ETH)"

    async def analyze(self, market_data: Dict[str, Any]) -> Signal:
        # Placeholder logic
        return None

    def calculate_entry_params(self, signal: Signal, wallet_balance: float) -> Dict[str, Any]:
        return {}
