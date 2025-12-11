class RiskManager:
    """
    The Guardian: Centralized Risk System.
    """
    def __init__(self, max_portfolio_exposure: float = 0.5):
        self.max_exposure = max_portfolio_exposure
        self.active_positions = {}
        self.portfolio_correlation = 0.0

    async def check_trade_approval(self, signal, current_exposure: float) -> bool:
        """
        Gatekeeper for new trades.
        """
        # 1. Global Exposure Limit
        if current_exposure >= self.max_exposure:
            print(f"🚫 Trade Rejected: Max Exposure ({self.max_exposure}) Reached.")
            return False
            
        # 2. Correlation Guard (Stub)
        if self.portfolio_correlation > 0.8 and signal.action == 'BUY':
             print(f"🚫 Trade Rejected: Portfolio too correlated ({self.portfolio_correlation}).")
             return False
             
        return True

    def calculate_real_breakeven(self, entry_price: float, fee_rate: float = 0.001, slippage: float = 0.0005) -> float:
        """
        Calculates the TRUE price to exit without loss.
        Includes Entry Fee + Exit Fee + Slippage Estimate.
        """
        # Fee is paid on Notional (Price * Size). Roughly 2x fee rate for roundtrip.
        total_friction = (fee_rate * 2) + slippage
        breakeven_price = entry_price * (1 + total_friction)
        return breakeven_price

    async def monitor_hedging_trigger(self, btc_price_change_pct: float):
        """
        Auto-Hedge Logic:
        If BTC crashes > 3% in short time, open shorts on high-beta alts.
        """
        if btc_price_change_pct < -0.03:
            print("🚨 SYSTEM ALERT: BTC CRASH DETECTED. TRIGGERING HEDGE SHORTS.")
            return True
        return False
