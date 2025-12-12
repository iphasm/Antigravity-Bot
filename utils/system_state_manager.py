
import json
import os
import logging
from typing import Dict, Any

STATE_FILE = "bot_state.json"

class SystemStateManager:
    def __init__(self, state_file=STATE_FILE):
        self.state_file = state_file
        self.default_state = {
            "enabled_strategies": {
                "SCALPING": False,
                "GRID": False,
                "MEAN_REVERSION": True
            },
            "group_config": {
                "CRYPTO": True,
                "STOCKS": False,
                "COMMODITY": False
            },
            "disabled_assets": [],
            "session_config": {
                "leverage": 5,
                "max_capital_pct": 0.1,
                "personality": "STANDARD_ES",
                "mode": "WATCHER"
            }
        }

    def load_state(self) -> Dict[str, Any]:
        """Loads state from JSON file, returning defaults if file missing or corrupt."""
        if not os.path.exists(self.state_file):
            print(f"⚠️ State file '{self.state_file}' not found. Using defaults.")
            return self.default_state.copy()

        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                state = json.load(f)
                # Merge with defaults to ensure all keys exist (migrations)
                merged_state = self.default_state.copy()
                
                # Deep merge for dictionaries
                for key, val in state.items():
                    if isinstance(val, dict) and key in merged_state:
                         merged_state[key].update(val)
                    else:
                        merged_state[key] = val
                
                print(f"✅ State loaded from '{self.state_file}'")
                return merged_state
        except Exception as e:
            print(f"❌ Error loading state: {e}. Using defaults.")
            return self.default_state.copy()

    def save_state(self, enabled_strategies: Dict, group_config: Dict, disabled_assets: set, session: Any = None):
        """Saves current runtime state to JSON."""
        
        # Extract session config if a session object is provided (assuming single session for now or taking first found)
        # In a multi-user scenario, this would need to save per-chat-id configs.
        # For this bot, we often treat the main chat as the primary session.
        
        session_cfg = self.default_state["session_config"]
        if session and session.config:
            session_cfg = session.config.copy()
            # Ensure mode is saved if it exists in config, otherwise default to WATCHER
            if 'mode' not in session_cfg:
                session_cfg['mode'] = 'WATCHER'

        state = {
            "enabled_strategies": enabled_strategies,
            "group_config": group_config,
            "disabled_assets": list(disabled_assets), # Convert set to list for JSON
            "session_config": session_cfg
        }

        try:
            with open(self.state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=4)
            # print("💾 State saved.") # Optional: Too verbose for every click
        except Exception as e:
            print(f"❌ Error saving state: {e}")
