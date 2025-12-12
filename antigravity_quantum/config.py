
# Dynamic configuration for the Quantum Engine
# This file is imported by both the Engine (background) and Main (foreground).
# Simple toggles. In a larger app, use a proper DB or Redis.

# --- STRATEGY CONFIG ---
ENABLED_STRATEGIES = {
    'SCALPING': False,      # High Risk, High Reward
    'GRID': False,          # Grid Trading for sideways
    'MEAN_REVERSION': True  # Default safe strategy
}

# Assets specifically allowed for Grid Trading (Whitelisted)
GRID_WHITELIST = ['ADA', 'ZEC'] 

# Assets specifically allowed for Scalping
# High Volatility assets only
SCALPING_WHITELIST = ['ZEC', 'SUI', 'SOL'] 

# Global Settings
USE_QUANTUM_ENGINE = True
