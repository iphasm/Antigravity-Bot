import os
import math
from binance.client import Client
from binance.enums import *
from binance.exceptions import BinanceAPIException

class BinanceManager:
    def __init__(self):
        self.api_key = os.getenv('BINANCE_API_KEY')
        self.api_secret = os.getenv('BINANCE_SECRET')
        self.client = None
        
        # Configuration
        self.leverage = int(os.getenv('LEVERAGE', 5))
        self.stop_loss_pct = float(os.getenv('STOP_LOSS_PCT', 0.02)) # 2% default
        self.max_capital_pct = float(os.getenv('MAX_CAPITAL_PCT', 0.10)) # 10% default
        
        # Proxy Config
        self.proxy_url = os.getenv('PROXY_URL')
        self.request_params = {'proxies': {'https': self.proxy_url}} if self.proxy_url else None

        if self.api_key and self.api_secret:
            try:
                self.client = Client(self.api_key, self.api_secret, tld='com', requests_params=self.request_params)
                proxy_msg = " [Proxy Enabled]" if self.proxy_url else ""
                print(f"✅ Binance Client initialized [International API]{proxy_msg}.")
            except Exception as e:
                print(f"❌ Failed to init Binance Client: {e}")
        else:
            print("⚠️ Binance API Keys missing in environment.")

    def get_symbol_precision(self, symbol):
        """Get quantity and price precision for a symbol"""
        try:
            info = self.client.futures_exchange_info()
            for s in info['symbols']:
                if s['symbol'] == symbol:
                    qty_precision = s['quantityPrecision']
                    price_precision = s['pricePrecision']
                    return qty_precision, price_precision
        except Exception as e:
            print(f"Error getting precision for {symbol}: {e}")
            return 2, 2

    def execute_long_position(self, symbol):
        if not self.client:
            print("❌ Execution skipped: No Binance Client.")
            return

        try:
            # 1. Update Leverage
            self.client.futures_change_leverage(symbol=symbol, leverage=self.leverage)

            # 2. Calculate Position Size
            # Get USDT Balance
            account = self.client.futures_account_balance()
            usdt_balance = next((float(a['balance']) for a in account if a['asset'] == 'USDT'), 0)
            
            if usdt_balance <= 0:
                print("❌ Insufficient USDT Balance.")
                return

            # Max amount to risk (Margin) = 10% of Balance
            margin_assignment = usdt_balance * self.max_capital_pct
            
            # Get Current Price
            ticker = self.client.futures_symbol_ticker(symbol=symbol)
            current_price = float(ticker['price'])
            
            # Calculate Quantity (Margin * Leverage / Price)
            # Example: $100 Margin * 5x = $500 Position. $500 / $50/coin = 10 coins.
            raw_quantity = (margin_assignment * self.leverage) / current_price
            
            # Adjust precision
            qty_precision, price_precision = self.get_symbol_precision(symbol)
            quantity = float(round(raw_quantity, qty_precision))
            
            print(f"⚖️ Sizing: Bal=${usdt_balance:.2f} | Margin=${margin_assignment:.2f} | Qty={quantity} {symbol}")

            # 3. Execute Market Buy
            order = self.client.futures_create_order(
                symbol=symbol,
                side=SIDE_BUY,
                type=ORDER_TYPE_MARKET,
                quantity=quantity
            )
            entry_price = float(order.get('avgPrice', current_price))
            print(f"✅ BUY Executed: {symbol} @ {entry_price}")

            # 4. Place Stop Loss (SL) & Take Profit (TP)
            # SL = Entry * (1 - SL_PCT)
            # TP = Entry * (1 + (SL_PCT * 3))
            
            sl_price = entry_price * (1 - self.stop_loss_pct)
            tp_price = entry_price * (1 + (self.stop_loss_pct * 3))
            
            # Round prices
            sl_price = round(sl_price, price_precision)
            tp_price = round(tp_price, price_precision)

            # Send Orders
            # Stop Loss
            self.client.futures_create_order(
                symbol=symbol,
                side=SIDE_SELL,
                type=ORDER_TYPE_STOP_MARKET,
                stopPrice=sl_price,
                closePosition=True
            )
            
            # Take Profit
            self.client.futures_create_order(
                symbol=symbol,
                side=SIDE_SELL,
                type=ORDER_TYPE_TAKE_PROFIT_MARKET,
                stopPrice=tp_price,
                closePosition=True
            )
            
            print(f"🛡️ SL @ {sl_price} | 🎯 TP @ {tp_price}")
            return True

        except BinanceAPIException as e:
            print(f"❌ Binance API Error: {e}")
        except Exception as e:
            print(f"❌ Error executing trade: {e}")
            return False
