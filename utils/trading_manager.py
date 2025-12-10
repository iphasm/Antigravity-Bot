import os
import json
import time
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
            "stop_loss_pct": 0.02
        }
        
        if config:
            self.config.update(config)

        # Proxy Setup: GLOBAL ONLY (Railway / Env)
        # We ignore session-specific proxy_url and enforce system proxy.
        self.request_params = None
        sys_proxy = os.getenv('PROXY_URL') or os.getenv('HTTPS_PROXY') or os.getenv('HTTP_PROXY')
        
        if sys_proxy:
             self.request_params = {'proxies': {'https': sys_proxy}}
             # Optional: Log only once or verbose
             # print(f"🌍 Using Global Proxy for Chat {self.chat_id}")

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
        return self.config[key]

    def get_configuration(self):
        return {
            "leverage": self.config['leverage'],
            "max_capital_pct": self.config['max_capital_pct'],
            "stop_loss_pct": self.config['stop_loss_pct'],
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

    def execute_long_position(self, symbol, atr=None):
        if not self.client:
            return False, "No valid API Keys provided for this chat."
            
        try:
            leverage = self.config['leverage']
            max_capital_pct = self.config['max_capital_pct']
            stop_loss_pct = self.config['stop_loss_pct']

            # 0. Safety Check: Existing Position
            # We fetch position info to ensure we don't double-buy
            positions = self.client.futures_position_information(symbol=symbol)
            # In One-Way Mode, len is 1. In Hedge Mode, len is 2 (Long/Short).
            # We assume we only want ONE net exposure per symbol.
            net_qty = 0.0
            for p in positions:
                net_qty += float(p['positionAmt'])
            
            if net_qty != 0:
                return False, f"⚠️ Position already open ({net_qty} {symbol})."

            # 1. Update Leverage
            self.client.futures_change_leverage(symbol=symbol, leverage=leverage)

            # 2. Calculate Position Size
            account = self.client.futures_account_balance()
            usdt_balance = next((float(a['availableBalance']) for a in account if a['asset'] == 'USDT'), 0)
            
            ticker = self.client.futures_symbol_ticker(symbol=symbol)
            current_price = float(ticker['price'])
            qty_precision, price_precision = self.get_symbol_precision(symbol)

            # --- DYNAMIC CALCULATION ---
            if atr and atr > 0:
                # Rule: SL = 2.0 * ATR
                sl_dist = 2.0 * atr
                sl_price = round(current_price - sl_dist, price_precision)
                
                # Rule: Risk Amount = 2% of Equity
                risk_amount = usdt_balance * 0.02 
                
                raw_quantity = risk_amount / sl_dist
                
                # Check Min Notional (Binance requires > 5 USDT)
                notional = raw_quantity * current_price
                if notional < 5.5:
                    raw_quantity = 5.5 / current_price # Bump to min
                
                # Check absolute margin limit
                notional = raw_quantity * current_price
                margin_req = notional / leverage
                
                if margin_req > (usdt_balance * max_capital_pct):
                     raw_quantity = (usdt_balance * max_capital_pct * leverage) / current_price
                
                tp1_price = round(current_price + (1.5 * sl_dist), price_precision)
                
            else:
                # --- FALLBACK (FIXED %) ---
                margin_assignment = usdt_balance * max_capital_pct
                raw_quantity = (margin_assignment * leverage) / current_price
                sl_price = round(current_price * (1 - stop_loss_pct), price_precision)
                tp1_price = round(current_price * (1 + (stop_loss_pct * 3)), price_precision) 

            quantity = float(round(raw_quantity, qty_precision))
            
            # --- PRE-FLIGHT CHECK ---
            final_notional = quantity * current_price
            if final_notional < 5.0:
                 return False, f"❌ Capital Insufficient for Valid Entry.\nRequired: >5.0 USDT Notional.\nCalculated: {final_notional:.2f} USDT.\nAction: Increase Capital or Risk %."

            if quantity <= 0: return False, "Position too small."

            # 3. Execute Market Buy
            order = self.client.futures_create_order(
                symbol=symbol, side='BUY', type='MARKET', quantity=quantity
            )
            entry_price = float(order.get('avgPrice', current_price))
            if entry_price == 0: entry_price = current_price

            # 4. Orders
            # SL (Full Size)
            if sl_price > 0:
                self.client.futures_create_order(
                    symbol=symbol, side='SELL', type='STOP_MARKET', stopPrice=sl_price, closePosition=True
                )
            
            # --- SPLIT ORDER LOGIC ---
            qty_tp1 = float(round(quantity / 2, qty_precision))
            tp_notional = qty_tp1 * entry_price
            
            if tp_notional < 5.5:
                # 🚫 Small Position: NO SPLIT (100% TP1)
                self.client.futures_create_order(
                   symbol=symbol, side='SELL', type='TAKE_PROFIT_MARKET', stopPrice=tp1_price, closePosition=True
                )
                success_msg = f"Long {symbol} (x{leverage})\nEntry: {entry_price}\nQty: {quantity}\nSL: {sl_price}\nTP: {tp1_price} (100% - Small Pos)"
            else:
                # ✅ Sufficient Size: SPLIT (50% TP1 + 50% Trailing)
                if qty_tp1 > 0:
                    self.client.futures_create_order(
                       symbol=symbol, side='SELL', type='TAKE_PROFIT_MARKET', stopPrice=tp1_price, quantity=qty_tp1
                    )
                    
                # TP2 (Trailing - Remainder)
                qty_tp2 = float(round(quantity - qty_tp1, qty_precision))
                if qty_tp2 > 0:
                     self.client.futures_create_order(
                        symbol=symbol, 
                        side='SELL', 
                        type='TRAILING_STOP_MARKET', 
                        callbackRate=1.5, 
                        quantity=qty_tp2
                    )
                success_msg = f"Long {symbol} (x{leverage})\nEntry: {entry_price}\nQty: {quantity}\nSL: {sl_price}\nTP1: {tp1_price} (50%)\nTP2: Trailing 1.5%"

            self._log_trade(symbol, entry_price, quantity, sl_price, tp1_price)
            return True, success_msg

        except BinanceAPIException as e:
            return False, f"Binance Error: {e.message}"
        except Exception as e:
            return False, f"Error: {str(e)}"

    def execute_short_position(self, symbol, atr=None):
        if not self.client:
            return False, "No valid API Keys provided for this chat."
            
        try:
            leverage = self.config['leverage']
            max_capital_pct = self.config['max_capital_pct']
            stop_loss_pct = self.config['stop_loss_pct']

            # 0. Safety Check
            positions = self.client.futures_position_information(symbol=symbol)
            net_qty = sum(float(p['positionAmt']) for p in positions)
            if net_qty != 0:
                return False, f"⚠️ Position already open ({net_qty} {symbol})."

            # 1. Update Leverage
            self.client.futures_change_leverage(symbol=symbol, leverage=leverage)

            # 2. Calculate Size & Params
            account = self.client.futures_account_balance()
            usdt_balance = next((float(a['availableBalance']) for a in account if a['asset'] == 'USDT'), 0)
            
            ticker = self.client.futures_symbol_ticker(symbol=symbol)
            current_price = float(ticker['price'])
            qty_precision, price_precision = self.get_symbol_precision(symbol)

            # --- DYNAMIC CALCULATION ---
            if atr and atr > 0:
                sl_dist = 2.0 * atr
                sl_price = round(current_price + sl_dist, price_precision) # Short SL is above
                
                risk_amount = usdt_balance * 0.02
                raw_quantity = risk_amount / sl_dist
                
                # Check Min Notional
                notional = raw_quantity * current_price
                if notional < 5.5:
                    raw_quantity = 5.5 / current_price

                notional = raw_quantity * current_price
                margin_req = notional / leverage
                
                if margin_req > (usdt_balance * max_capital_pct):
                     raw_quantity = (usdt_balance * max_capital_pct * leverage) / current_price
                
                tp1_price = round(current_price - (1.5 * sl_dist), price_precision) # Short TP is below
                
            else:
                margin_assignment = usdt_balance * max_capital_pct
                raw_quantity = (margin_assignment * leverage) / current_price
                sl_price = round(current_price * (1 + stop_loss_pct), price_precision)
                tp1_price = round(current_price * (1 - (stop_loss_pct * 3)), price_precision)

            quantity = float(round(raw_quantity, qty_precision))
            
            # --- PRE-FLIGHT CHECK ---
            final_notional = quantity * current_price
            if final_notional < 5.0:
                 return False, f"❌ Capital Insufficient for Valid Entry.\nRequired: >5.0 USDT Notional.\nCalculated: {final_notional:.2f} USDT.\nAction: Increase Capital or Risk %."

            if quantity <= 0: return False, "Position too small."

            # 3. Execute Market SELL
            order = self.client.futures_create_order(
                symbol=symbol, side='SELL', type='MARKET', quantity=quantity
            )
            entry_price = float(order.get('avgPrice', current_price))

            # 4. Orders
            # SL (Full Size)
            if sl_price > 0:
                 self.client.futures_create_order(
                    symbol=symbol, side='BUY', type='STOP_MARKET', stopPrice=sl_price, closePosition=True
                )
            
            # --- SPLIT ORDER LOGIC ---
            qty_tp1 = float(round(quantity / 2, qty_precision))
            tp_notional = qty_tp1 * entry_price
            
            if tp_notional < 5.5:
                # 🚫 Small Position: NO SPLIT (100% TP1)
                self.client.futures_create_order(
                   symbol=symbol, side='BUY', type='TAKE_PROFIT_MARKET', stopPrice=tp1_price, closePosition=True
                )
                success_msg = f"Short {symbol} (x{leverage})\nEntry: {entry_price}\nQty: {quantity}\nSL: {sl_price}\nTP: {tp1_price} (100% - Small Pos)"
            else:
                 # ✅ Sufficient Size: SPLIT (50% TP1 + 50% Trailing)
                if qty_tp1 > 0:
                    self.client.futures_create_order(
                       symbol=symbol, side='BUY', type='TAKE_PROFIT_MARKET', stopPrice=tp1_price, quantity=qty_tp1
                    )
                
                qty_tp2 = float(round(quantity - qty_tp1, qty_precision))
                if qty_tp2 > 0:
                     self.client.futures_create_order(
                        symbol=symbol, 
                        side='BUY', 
                        type='TRAILING_STOP_MARKET', 
                        callbackRate=1.5, 
                        quantity=qty_tp2
                    )
                success_msg = f"Short {symbol} (x{leverage})\nEntry: {entry_price}\nQty: {quantity}\nSL: {sl_price}\nTP1: {tp1_price} (50%)\nTP2: Trailing 1.5%"

            self._log_trade(symbol, entry_price, quantity, sl_price, tp1_price, side='SHORT')
            return True, success_msg

        except BinanceAPIException as e:
            return False, f"Binance Error: {e.message}"
        except Exception as e:
            return False, f"Error: {e}"

    def execute_close_all(self):
        """Closes ALL active positions"""
        if not self.client: return False, "No valid session."
        
        active_pos = self.get_active_positions()
        if not active_pos:
            return False, "No active positions to close."
            
        results = []
        for p in active_pos:
            sym = p['symbol']
            success, msg = self.execute_close_position(sym)
            results.append(f"{sym}: {'✅' if success else '❌'}")
            
        return True, "Batch Close:\n" + "\n".join(results)

    def execute_close_position(self, symbol):
        """Closes all positions and open orders for a symbol"""
        if not self.client: return False, "No valid session."
        
        try:
            # 1. Cancel Open Orders (SL/TP)
            self.client.futures_cancel_all_open_orders(symbol=symbol)
            
            # 2. Get Position Info
            try:
                positions = self.client.futures_position_information(symbol=symbol)
            except:
                # Fallback for some library versions that return list
                positions = self.client.futures_position_information()
                
            qty = 0.0
            for p in positions:
                if p['symbol'] == symbol:
                    qty = float(p['positionAmt'])
                    break
            
            if qty == 0:
                return False, f"No open position found for {symbol}."
            
            # 3. Close Position
            side = 'SELL' if qty > 0 else 'BUY'
            
            self.client.futures_create_order(
                symbol=symbol, 
                side=side, 
                type='MARKET', 
                reduceOnly=True,
                quantity=abs(qty)
            )
            
            return True, f"✅ Closed {symbol} ({qty}). PnL pending update."
            
        except BinanceAPIException as e:
            return False, f"Binance Error: {e.message}"
        except Exception as e:
            return False, f"Error: {str(e)}"

    def get_pnl_history(self, days=1):
        """Fetches Realized PnL from Binance for the last N days"""
        if not self.client: return 0.0, []
        
        try:
            start_time = int((time.time() - (days * 86400)) * 1000)
            
            # Fetch Realized PnL
            income = self.client.futures_income_history(
                incomeType='REALIZED_PNL', 
                startTime=start_time,
                limit=100
            )
            # Fetch Commission (to subtract for Net PnL)
            commission = self.client.futures_income_history(
                incomeType='COMMISSION', 
                startTime=start_time,
                limit=100
            )
            
            total_pnl = 0.0
            details = []
            
            # Process PnL
            for item in income:
                amt = float(item['income'])
                total_pnl += amt
                details.append({'symbol': item['symbol'], 'amount': amt, 'time': item['time'], 'type': 'PNL'})
            
            # Process Commission
            for item in commission:
                amt = float(item['income'])
                total_pnl += amt # Commission is negative, so adding subtracts it
                # details.append({'symbol': item['symbol'], 'amount': amt, 'time': item['time'], 'type': 'COMM'})

            return total_pnl, details
            
        except Exception as e:
            print(f"Error fetching PnL: {e}")
            return 0.0, []

    def get_wallet_details(self):
        """
        Returns full wallet details:
        - Spot Balance (Total USDT estimate if possible, or just USDT free)
        - Futures Balance (Margin Balance)
        - Futures PnL (Unrealized)
        """
        if not self.client: return {}
        
        details = {
            "spot_usdt": 0.0,
            "futures_balance": 0.0,
            "futures_pnl": 0.0,
            "futures_total": 0.0
        }
        
        try:
            # 1. FUTURES
            acc_fut = self.client.futures_account()
            details['futures_balance'] = float(acc_fut.get('availableBalance', 0)) # Available for Trade
            details['futures_total'] = float(acc_fut.get('totalMarginBalance', 0)) # Equity (Bal + PnL)
            details['futures_pnl'] = float(acc_fut.get('totalUnrealizedProfit', 0))
            
            # 2. SPOT
            # We want at least USDT. 
            # Ideally we want Total Net Asset Value but that requires ticker prices for all assets.
            # Let's start with USDT Free + Locked
            acc_spot = self.client.get_account()
            spot_usdt = 0.0
            
            for bal in acc_spot['balances']:
                if bal['asset'] == 'USDT':
                    spot_usdt = float(bal['free']) + float(bal['locked'])
                    break
            
            details['spot_usdt'] = spot_usdt
            
            details['spot_usdt'] = spot_usdt

            # 3. EARN (Flexible + Locked)
            earn_usdt = 0.0
            try:
                # Flexible
                flex_pos = self.client.get_simple_earn_flexible_position()
                for p in flex_pos:
                     if 'USDT' in p['asset']: # Matches USDT, LDUSDT etc
                         earn_usdt += float(p['totalAmount'])
                
                # Locked
                locked_pos = self.client.get_simple_earn_locked_position()
                for p in locked_pos:
                     if 'USDT' in p['asset']:
                         earn_usdt += float(p['amount']) # 'amount' usually for locked
                         
            except Exception as e: 
                print(f"Earn fetch error: {e}")
            
            details['earn_usdt'] = earn_usdt
            
            return details
            
        except Exception as e:
            print(f"Error fetching wallet: {e}")
            return details


    def _log_trade(self, symbol, entry, qty, sl, tp, side='LONG'):
        """Logs trade to local JSON file for history"""
        try:
            log_file = 'data/trades.json'
            entry_data = {
                "timestamp": time.time(),
                "date": time.strftime('%Y-%m-%d %H:%M:%S'),
                "chat_id": self.chat_id,
                "symbol": symbol,
                "side": side,
                "entry_price": entry,
                "quantity": qty,
                "sl": sl,
                "tp": tp
            }
            
            data = []
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    try:
                        data = json.load(f)
                    except: pass # Handle corrupt file
            
            data.append(entry_data)
            
            with open(log_file, 'w') as f:
                json.dump(data, f, indent=4)
                
        except Exception as e:
            print(f"⚠️ Failed to log trade: {e}")

    def get_active_positions(self):
        """Returns list of symbols with active positions"""
        if not self.client: return []
        try:
            positions = self.client.futures_position_information()
            active = []
            for p in positions:
                if float(p['positionAmt']) != 0:
                    active.append({
                        "symbol": p['symbol'],
                        "amt": p['positionAmt'],
                        "entry": p['entryPrice'],
                        "pnl": p['unRealizedProfit']
                    })
            return active
        except Exception as e:
            print(f"Error fetching positions: {e}")
            return []


class SessionManager:
    """
    Manages multiple TradingSessions backed by a JSON file.
    """
    def __init__(self, data_file='data/sessions.json'):
        self.data_file = data_file
        self.sessions = {} # chat_id -> TradingSession
        self._load_sessions()
        self._ensure_admin_session_from_env()

    def _ensure_admin_session_from_env(self):
        """
        Auto-loads admin session if environment variables are present.
        Prioritizes environment variables for the Admin ID.
        """
        admin_id = os.getenv('TELEGRAM_ADMIN_ID')
        
        # Support multiple naming conventions
        api_key = os.getenv('BINANCE_API_KEY') or os.getenv('BINANCE_KEY') or os.getenv('API_KEY')
        api_secret = os.getenv('BINANCE_SECRET') or os.getenv('BINANCE_API_SECRET') or os.getenv('SECRET_KEY')
        
        if admin_id and api_key and api_secret:
            print(f"👑 Admin ID {admin_id} detected in Env. Auto-configuring session...")
            # We create or update, but we DO NOT save to disk to avoid leaking Env keys into JSON
            # This session will exist in memory.
            
            # Check if session exists
            if str(admin_id) in self.sessions:
                # Update existing session in memory with env keys (overrides file)
                self.sessions[str(admin_id)].api_key = api_key
                self.sessions[str(admin_id)].api_secret = api_secret
                self.sessions[str(admin_id)]._init_client()
            else:
                # Create new in-memory session
                self.sessions[str(admin_id)] = TradingSession(
                    chat_id=str(admin_id),
                    api_key=api_key,
                    api_secret=api_secret
                )
            print("✅ Admin Session Auto-Configured from Environment.")

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

