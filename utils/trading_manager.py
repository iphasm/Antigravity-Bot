import os
import json
import threading
from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException

class TradingSession:
    """
    Represents a single trading session for a specific chat_id.
    Holds its own API keys and risk configuration.
    """
    def __init__(self, chat_id, api_key, api_secret, config=None):
        self.chat_id = chat_id
        self.api_key = api_key
        self.api_secret = api_secret
        self.client = None
        
        # Default Config
        self.config = {
            "leverage": 5,
            "max_capital_pct": 0.10,
            "stop_loss_pct": 0.02,
            "proxy_url": None
        }
        
        if config:
            self.config.update(config)

        # Proxy Setup from Config or Global Env (Optional fallback for proxy only)
        # Note: We prioritize session config for proxy if set
        self.request_params = None
        if self.config.get('proxy_url'):
             self.request_params = {'proxies': {'https': self.config['proxy_url']}}

        # Initialize Client
        self._init_client()

    def _init_client(self):
        if self.api_key and self.api_secret:
            try:
                self.client = Client(self.api_key, self.api_secret, tld='com', requests_params=self.request_params)
                print(f"✅ [Chat {self.chat_id}] Binance Client Initialized.")
            except Exception as e:
                print(f"❌ [Chat {self.chat_id}] Failed to init Client: {e}")
                self.client = None
        else:
            print(f"⚠️ [Chat {self.chat_id}] Missing API Keys.")

    # --- CONFIGURATION METHODS ---
    def update_config(self, key, value):
        self.config[key] = value
        # If proxy changed, re-init might be needed, but usually leverage/risk doesn't need re-init
        return self.config[key]

    def get_configuration(self):
        return {
            "leverage": self.config['leverage'],
            "max_capital_pct": self.config['max_capital_pct'],
            "stop_loss_pct": self.config['stop_loss_pct'],
            "proxy_enabled": bool(self.config.get('proxy_url')),
            "has_keys": bool(self.client) # Status check
        }

    def get_symbol_precision(self, symbol):
        if not self.client: return 2, 2
        try:
            info = self.client.futures_exchange_info()
            for s in info['symbols']:
                if s['symbol'] == symbol:
                    return s['quantityPrecision'], s['pricePrecision']
        except Exception as e:
            print(f"Error getting precision for {symbol}: {e}")
        return 2, 2

    def execute_long_position(self, symbol):
        if not self.client:
            return False, "No valid API Keys provided for this chat."
            
        try:
            leverage = self.config['leverage']
            max_capital_pct = self.config['max_capital_pct']
            stop_loss_pct = self.config['stop_loss_pct']

            # 1. Update Leverage
            self.client.futures_change_leverage(symbol=symbol, leverage=leverage)

            # 2. Calculate Position Size
            account = self.client.futures_account_balance()
            usdt_balance = next((float(a['availableBalance']) for a in account if a['asset'] == 'USDT'), 0)
            
            if usdt_balance <= 0:
                return False, f"Insufficient USDT Balance: ${usdt_balance:.2f}"

            margin_assignment = usdt_balance * max_capital_pct
            
            ticker = self.client.futures_symbol_ticker(symbol=symbol)
            current_price = float(ticker['price'])
            
            raw_quantity = (margin_assignment * leverage) / current_price
            
            qty_precision, price_precision = self.get_symbol_precision(symbol)
            quantity = float(round(raw_quantity, qty_precision))
            
            if quantity <= 0:
                return False, f"Position too small for ${margin_assignment:.2f} margin."

            # 3. Execute Market Buy
            order = self.client.futures_create_order(
                symbol=symbol, side='BUY', type='MARKET', quantity=quantity
            )
            entry_price = float(order.get('avgPrice', current_price))
            if entry_price == 0: entry_price = current_price

            # 4. Stop Loss & Take Profit
            sl_price = round(entry_price * (1 - stop_loss_pct), price_precision)
            tp_price = round(entry_price * (1 + (stop_loss_pct * 3)), price_precision)
            
            if sl_price <= 0:
                return True, "Executed, but SL calculation failed (<=0)."

            self.client.futures_create_order(
                symbol=symbol, side='SELL', type='STOP_MARKET', stopPrice=sl_price, closePosition=True
            )
            self.client.futures_create_order(
                symbol=symbol, side='SELL', type='TAKE_PROFIT_MARKET', stopPrice=tp_price, closePosition=True
            )
            
            return True, f"Long {symbol} @ {entry_price} (SL: {sl_price}, TP: {tp_price})"

        except BinanceAPIException as e:
            return False, f"Binance Error: {e.message}"
        except Exception as e:
            return False, f"Error: {str(e)}"


class SessionManager:
    """
    Manages multiple TradingSessions backed by a JSON file.
    """
    def __init__(self, data_file='data/sessions.json'):
        self.data_file = data_file
        self.sessions = {} # chat_id -> TradingSession
        self._load_sessions()

    def _load_sessions(self):
        if not os.path.exists(self.data_file):
            # Create data dir if not exists
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            with open(self.data_file, 'w') as f:
                json.dump({}, f)
            return

        try:
            with open(self.data_file, 'r') as f:
                data = json.load(f)
                for chat_id, s_data in data.items():
                    self.sessions[chat_id] = TradingSession(
                        chat_id=chat_id,
                        api_key=s_data.get('api_key'),
                        api_secret=s_data.get('api_secret'),
                        config=s_data.get('config')
                    )
            print(f"📚 Loaded {len(self.sessions)} trading sessions.")
        except Exception as e:
            print(f"❌ Failed to load sessions: {e}")

    def save_sessions(self):
        data = {}
        for chat_id, session in self.sessions.items():
            data[chat_id] = {
                "api_key": session.api_key,
                "api_secret": session.api_secret,
                "config": session.config
            }
        
        try:
            with open(self.data_file, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            print(f"❌ Failed to save sessions: {e}")

    def get_session(self, chat_id):
        return self.sessions.get(str(chat_id))

    def create_or_update_session(self, chat_id, api_key, api_secret):
        chat_id = str(chat_id)
        if chat_id in self.sessions:
            # Update Keys
            self.sessions[chat_id].api_key = api_key
            self.sessions[chat_id].api_secret = api_secret
            self.sessions[chat_id]._init_client() # Re-init client
        else:
            # Create New
            self.sessions[chat_id] = TradingSession(chat_id, api_key, api_secret)
        
        self.save_sessions()
        return self.sessions[chat_id]
    
    def delete_session(self, chat_id):
        chat_id = str(chat_id)
        if chat_id in self.sessions:
            del self.sessions[chat_id]
            self.save_sessions()
            return True
        return False
    
    def get_all_sessions(self):
        return list(self.sessions.values())

