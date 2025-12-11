import os
import json
import time
import threading
from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException
# --- ALPACA IMPORTS ---
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest, TakeProfitRequest, StopLossRequest
from alpaca.trading.enums import OrderSide, TimeInForce

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
            "spot_allocation_pct": 0.20 # Default 20% for Spot Buys
        }
        
        if config:
            self.config.update(config)

        # Automation Mode: WATCHER (Default), COPILOT, PILOT
        self.mode = self.config.get('mode', 'WATCHER')

        # Proxy Setup: GLOBAL ONLY (Railway / Env)
        # We ignore session-specific proxy_url and enforce system proxy.
        self.request_params = None
        sys_proxy = os.getenv('PROXY_URL') or os.getenv('HTTPS_PROXY') or os.getenv('HTTP_PROXY')
        
        if sys_proxy:
             self.request_params = {'proxies': {'https': sys_proxy}}
             # Optional: Log only once or verbose
             # print(f"🌍 Using Global Proxy for Chat {self.chat_id}")

        # Initialize Client
        self.alpaca_client = None
        self._init_client()

    def _init_client(self):
        # 1. BINANCE
        if self.api_key and self.api_secret:
            try:
                self.client = Client(self.api_key, self.api_secret, tld='com', requests_params=self.request_params)
                print(f"✅ [Chat {self.chat_id}] Binance Client Initialized.")
            except Exception as e:
                print(f"❌ [Chat {self.chat_id}] Failed to init Client: {e}")
                self.client = None
        else:
            print(f"⚠️ [Chat {self.chat_id}] Missing API Keys.")
            
        # 2. ALPACA (Env Vars only)
        ak = os.getenv('APCA_API_KEY_ID')
        ask = os.getenv('APCA_API_SECRET_KEY')
        base_url = os.getenv('APCA_API_BASE_URL') 
        
        # Determine paper mode default
        paper = True 
        if base_url:
            # Sanitize URL: alpaca-py appends /v2 automatically for many calls. 
            # If user provides .../v2, strip it to avoid .../v2/v2/orders (404 Not Found)
            if base_url.endswith('/v2'):
                base_url = base_url[:-3]
            elif base_url.endswith('/v2/'):
                base_url = base_url[:-4]
            
            # Simple check for paper/live
            if 'paper' not in base_url and 'api.alpaca' in base_url:
                paper = False
        
        if ak and ask:
            try:
                # Pass url_override if set, otherwise rely on paper=True/False defaults
                self.alpaca_client = TradingClient(ak, ask, paper=paper, url_override=base_url)
                print(f"✅ [Chat {self.chat_id}] Alpaca Client Initialized (Paper: {paper}, URL: {base_url or 'Default'})")
            except Exception as e:
                print(f"❌ [Chat {self.chat_id}] Failed to init Alpaca: {e}")

    # --- CONFIGURATION METHODS ---
    def set_mode(self, mode):
        if mode in ['WATCHER', 'COPILOT', 'PILOT']:
            self.mode = mode
            self.config['mode'] = mode
            return True
        return False

    def update_config(self, key, value):
        self.config[key] = value
        return self.config[key]

    def get_configuration(self):
        return {
            "mode": self.mode,
            "leverage": self.config['leverage'],
            "max_capital_pct": self.config['max_capital_pct'],
            "stop_loss_pct": self.config['stop_loss_pct'],
            "leverage": self.config['leverage'],
            "max_capital_pct": self.config['max_capital_pct'],
            "stop_loss_pct": self.config['stop_loss_pct'],
            "spot_allocation_pct": self.config.get('spot_allocation_pct', 0.20),
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

    def _execute_alpaca_order(self, symbol, side, atr=None):
        if not self.alpaca_client:
            return False, "⚠️ Alpaca Client not initialized (Check env vars)."

        try:
            # 1. Check existing position
            try:
                pos = self.alpaca_client.get_open_position(symbol)
                if pos:
                    return False, f"⚠️ Position already open for {symbol} ({pos.qty})."
            except:
                pass # No position found

            # 2. Get Account Info
            acct = self.alpaca_client.get_account()
            equity = float(acct.equity) if hasattr(acct, 'equity') else 100000.0

            # 3. Get Price (Quick Snapshot via YF)
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            # Use fast_info for speed, fallback to history
            try:
                current_price = ticker.fast_info['last_price']
            except:
                hist = ticker.history(period="1d")
                if not hist.empty:
                     current_price = hist['Close'].iloc[-1]
                else: 
                     return False, f"❌ Failed to fetch price for {symbol}"

            if not current_price: return False, "❌ Price is zero/null."

            # 4. Calculate Sizing
            risk_pct = 0.02 # 2% risk
            
            # SL / TP
            if atr and atr > 0:
                sl_dist = 2.0 * atr
                if side == 'LONG':
                    sl_price = current_price - sl_dist
                    tp_price = current_price + (1.5 * sl_dist)
                else: 
                    sl_price = current_price + sl_dist
                    tp_price = current_price - (1.5 * sl_dist)
            else:
                # Fallback 2% SL
                sl_pct = 0.02
                if side == 'LONG':
                    sl_price = current_price * (1 - sl_pct)
                    tp_price = current_price * (1 + (sl_pct * 3))
                else:
                    sl_price = current_price * (1 + sl_pct)
                    tp_price = current_price * (1 - (sl_pct * 3))

            dist_to_stop = abs(current_price - sl_price)
            if dist_to_stop == 0: dist_to_stop = 0.01

            # Units = (Equity * Risk) / Distance
            risk_amt = equity * risk_pct
            qty = risk_amt / dist_to_stop
            
            # Check Max Allocation (20% max per stock)
            max_alloc = equity * 0.20
            if (qty * current_price) > max_alloc:
                qty = max_alloc / current_price

            qty = round(qty, 2) 
            if qty < 0.01: return False, f"Calculated qty too small ({qty})."

            # 5. Order Request (Bracket)
            side_enum = OrderSide.BUY if side == 'LONG' else OrderSide.SELL
            
            req = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side_enum,
                time_in_force=TimeInForce.DAY,
                take_profit=TakeProfitRequest(limit_price=round(tp_price, 2)),
                stop_loss=StopLossRequest(stop_price=round(sl_price, 2))
            )

            res = self.alpaca_client.submit_order(req)
            
            # Escape underscores in status (e.g. partially_filled -> partially\_filled)
            status_str = str(res.status).replace('_', ' ') # Replace with space is cleaner than escaping
            
            return True, f"✅ Alpaca {side} {symbol}\nQty: {qty}\nSL: {sl_price:.2f}\nTP: {tp_price:.2f}\nStatus: {status_str}"

        except Exception as e:
            return False, f"Alpaca Error: {e}"

    def execute_long_position(self, symbol, atr=None):
        # Dispatch: Stocks (Alpaca) vs Crypto (Binance)
        if 'USDT' not in symbol:
             return self._execute_alpaca_order(symbol, 'LONG', atr)

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
            # Use futures_account for unified balance view
            acc_info = self.client.futures_account()
            
            # AVAILABLE BALANCE (For Check)
            available_balance = float(acc_info.get('availableBalance', 0))
            
            # TOTAL EQUITY (For Sizing) - Use this so position size doesn't shrink with open trades
            total_equity = float(acc_info.get('totalMarginBalance', 0))
            
            ticker = self.client.futures_symbol_ticker(symbol=symbol)
            current_price = float(ticker['price'])
            qty_precision, price_precision = self.get_symbol_precision(symbol)

            # --- DYNAMIC CALCULATION ---
            if atr and atr > 0:
                # Rule: SL = 2.0 * ATR
                sl_dist = 2.0 * atr
                sl_price = round(current_price - sl_dist, price_precision)
                
                # Rule: Risk Amount = 2% of Equity
                risk_amount = total_equity * 0.02 
                
                raw_quantity = risk_amount / sl_dist
                
                # Check Min Notional (Binance requires > 5 USDT)
                notional = raw_quantity * current_price
                if notional < 5.5:
                    raw_quantity = 5.5 / current_price # Bump to min
                
                # Check absolute margin limit
                notional = raw_quantity * current_price
                margin_req = notional / leverage
                
                if margin_req > (total_equity * max_capital_pct):
                     raw_quantity = (total_equity * max_capital_pct * leverage) / current_price
                
                tp1_price = round(current_price + (1.5 * sl_dist), price_precision)
                
            else:
                # --- FALLBACK (FIXED %) ---
                margin_assignment = total_equity * max_capital_pct
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
            try:
                order = self.client.futures_create_order(
                    symbol=symbol, side='BUY', type='MARKET', quantity=quantity
                )
                entry_price = float(order.get('avgPrice', current_price))
                if entry_price == 0: entry_price = current_price
            except Exception as e:
                return False, f"❌ Failed to Open Position: {e}"

            # 4. Post-Entry Orders (SL / TP) - ATOMIC SAFETY BLOCK
            try:
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

            except Exception as e:
                # 🚨 CRITICAL: ROLLBACK (Close Position)
                print(f"⚠️ Order Placement Failed: {e}. closing position...")
                try:
                     self.client.futures_create_order(
                        symbol=symbol, side='SELL', type='MARKET', quantity=quantity, reduceOnly=True
                    )
                except: pass # Best effort
                return False, f"⚠️ Error placing SL/TP ({e}). Position CLOSED for safety."

        except BinanceAPIException as e:
            return False, f"Binance Error: {e.message}"
        except Exception as e:
            return False, f"Error: {str(e)}"

    def execute_short_position(self, symbol, atr=None):
        if 'USDT' not in symbol:
             return self._execute_alpaca_order(symbol, 'SHORT', atr)

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
            acc_info = self.client.futures_account()
            
            # AVAILABLE BALANCE (For Check)
            available_balance = float(acc_info.get('availableBalance', 0))
            
            # TOTAL EQUITY (For Sizing)
            total_equity = float(acc_info.get('totalMarginBalance', 0))
            
            ticker = self.client.futures_symbol_ticker(symbol=symbol)
            current_price = float(ticker['price'])
            qty_precision, price_precision = self.get_symbol_precision(symbol)

            # --- DYNAMIC CALCULATION ---
            if atr and atr > 0:
                sl_dist = 2.0 * atr
                sl_price = round(current_price + sl_dist, price_precision) # Short SL is above
                
                risk_amount = total_equity * 0.02
                raw_quantity = risk_amount / sl_dist
                
                # Check Min Notional
                notional = raw_quantity * current_price
                if notional < 5.5:
                    raw_quantity = 5.5 / current_price

                notional = raw_quantity * current_price
                margin_req = notional / leverage
                
                if margin_req > (total_equity * max_capital_pct):
                     raw_quantity = (total_equity * max_capital_pct * leverage) / current_price
                
                tp1_price = round(current_price - (1.5 * sl_dist), price_precision) # Short TP is below
                
            else:
                margin_assignment = total_equity * max_capital_pct
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
            try:
                order = self.client.futures_create_order(
                    symbol=symbol, side='SELL', type='MARKET', quantity=quantity
                )
                entry_price = float(order.get('avgPrice', current_price))
            except Exception as e:
                return False, f"❌ Failed to Open Position: {e}"

            # 4. Post-Entry Orders (SL / TP) - ATOMIC SAFETY BLOCK
            try:
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

            except Exception as e:
                # 🚨 CRITICAL: ROLLBACK (Close Position)
                print(f"⚠️ Order Placement Failed: {e}. closing position...")
                try:
                     self.client.futures_create_order(
                        symbol=symbol, side='BUY', type='MARKET', quantity=quantity, reduceOnly=True
                    )
                except: pass 
                return False, f"⚠️ Error placing SL/TP ({e}). Position CLOSED for safety."

        except BinanceAPIException as e:
            return False, f"Binance Error: {e.message}"
        except Exception as e:
            return False, f"Error: {e}"

    def execute_close_all(self):
        """Cierra TODAS las posiciones activas"""
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
        """Cierra posiciones y órdenes abiertas para un símbolo"""
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

    def execute_spot_buy(self, symbol):
        """Ejecuta compra de mercado SPOT (Binance)"""
        if not self.client: return False, "No valid keys."
        
        try:
            # 1. Check Balance
            # For Spot, we need 'FREE' USDT
            acc = self.client.get_account()
            usdt_bal = 0.0
            for b in acc['balances']:
                if b['asset'] == 'USDT':
                    usdt_bal = float(b['free'])
                    break
            
            # 2. Allocation Logic (Dynamic)
            alloc_pct = self.config.get('spot_allocation_pct', 0.20)
            amount_to_spend = usdt_bal * alloc_pct
            
            if amount_to_spend < 6.0:
                 return False, f"❌ Insufficient Spot USDT (${usdt_bal:.2f}). Need >$6 to trade."
            
            # 3. Execute
            order = self.client.create_order(
                symbol=symbol,
                side='BUY',
                type='MARKET',
                quoteOrderQty=round(amount_to_spend, 2)
            )
            
            # 4. Result
            executed_qty = float(order.get('executedQty', 0))
            cummulative_quote_qty = float(order.get('cummulativeQuoteQty', 0))
            avg_price = cummulative_quote_qty / executed_qty if executed_qty else 0
            
            self._log_trade(symbol, avg_price, executed_qty, 0, 0, side='SPOT_BUY')
            return True, f"✅ SPOT BUY: {symbol}\nSpent: ${cummulative_quote_qty:.2f}\nQty: {executed_qty}\nAvg: {avg_price:.4f}"

        except BinanceAPIException as e:
            return False, f"Binance Spot Error: {e.message}"
        except Exception as e:
            return False, f"Error: {e}"

    def check_circuit_breaker(self):
        """
        Circuit Breaker / Switch de Seguridad
        Si detecta 5 pérdidas CONSECUTIVAS (Realized PnL < 0) en modo PILOT,
        baja automáticamente a COPILOT para detener la hemorragia.
        Returns: (Triggered: bool, Message: str)
        """
        if self.mode != 'PILOT':
             return False, ""
             
        if not self.client:
             return False, ""
             
        try:
            # Fetch last 20 Income entries (REALIZED_PNL only)
            income = self.client.futures_income_history(incomeType='REALIZED_PNL', limit=20)
            
            # Sort descending by time (Newest first)
            income.sort(key=lambda x: x['time'], reverse=True)
            
            consecutive_losses = 0
            for trade in income:
                pnl = float(trade['income'])
                if pnl < 0:
                    consecutive_losses += 1
                else:
                    # Found a win or zero, break the streak
                    break
            
            # Threshold Check
            if consecutive_losses >= 5:
                # Trigger Circuit Breaker
                old_mode = self.mode
                self.set_mode('COPILOT')
                
                msg = (
                    f"⚠️ **CIRCUIT BREAKER ACTIVADO** ⚠️\n"
                    f"Se han detectado {consecutive_losses} pérdidas consecutivas en modo PILOT.\n"
                    f"🛡️ El sistema ha cambiado automáticamente a **COPILOT** para proteger tu capital.\n"
                    f"Revisa el mercado manualmente antes de reactivar."
                )
                return True, msg
                
        except Exception as e:
            print(f"Error checking circuit breaker: {e}")
            
        return False, ""

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
            
            # 1b. ALPACA
            details['alpaca_equity'] = 0.0
            if self.alpaca_client:
                try:
                    acct = self.alpaca_client.get_account()
                    details['alpaca_equity'] = float(acct.equity)
                except Exception as e:
                    print(f"Alpaca Wallet Error: {e}")

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
        """Registra la operación en un JSON local para historial"""
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
        """Devuelve lista de símbolos con posiciones activas"""
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
            
            # 2. ALPACA
            if self.alpaca_client:
                try:
                    apos = self.alpaca_client.get_all_positions()
                    for p in apos:
                        active.append({
                            "symbol": p.symbol,
                            "amt": p.qty,
                            "entry": p.avg_entry_price,
                            "pnl": p.unrealized_pl
                        })
                except Exception as e:
                    print(f"Alpaca Positions Error: {e}")

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

