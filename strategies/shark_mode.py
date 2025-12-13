import threading
import time
import requests
import logging
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
import random

# Configure Logger for Railway
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [SHARK] - %(message)s')
logger = logging.getLogger("SharkMode")

class SharkSentinel(threading.Thread):
    def __init__(self, session_manager, notify_callback, crash_threshold_pct=3.0, window_seconds=60):
        """
        :param session_manager: Instance of SessionManager to access all active sessions.
        :param notify_callback: Function(msg) to send Telegram alerts.
        :param crash_threshold_pct: Percentage drop (positive float) to trigger Shark Mode (e.g. 3.0 for 3%).
        :param window_seconds: Rolling window size in seconds (O(1) memory check).
        """
        super().__init__()
        self.session_manager = session_manager
        self.notify_callback = notify_callback
        self.threshold = crash_threshold_pct
        self.window_seconds = window_seconds
        
        # Deque: Stores (timestamp, price)
        self.price_window = deque(maxlen=window_seconds + 10) 
        self.running = True
        self.triggered = False # Cooldown flag
        self.daemon = True # Auto-kill when main dies

        # Panic Targets (Configurable)
        self.sniper_targets = ['ETHUSDT', 'SOLUSDT', 'BNBUSDT']

    def exponential_backoff(self, func, *args, max_retries=3, **kwargs):
        """
        Executes func with exponential backoff on failure.
        Handling 502/504/System Busy errors.
        """
        delay = 1.0
        for i in range(max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Try {i+1}/{max_retries} failed: {e}")
                if i == max_retries - 1:
                    raise e
                time.sleep(delay + random.uniform(0, 0.5)) # Jitter
                delay *= 2

    def fetch_btc_price_raw(self):
        """Ultra-lightweight raw price fetch (bypassing main fetcher logic)."""
        url = "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT"
        try:
            resp = requests.get(url, timeout=2)
            data = resp.json()
            return float(data['price'])
        except Exception as e:
            logger.warning(f"Price fetch failed: {e}")
            return None

    def execute_defense_sequence(self):
        """
        PARALLEL EXECUTION:
        1. Panic Close ALL Longs (All Sessions)
        2. Sniper Short Targets (All Sessions)
        """
        logger.warning("⚔️ EXECUTING DEFENSE SEQUENCE ⚔️")
        
        sessions = self.session_manager.get_all_sessions()
        if not sessions:
            return

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []

            # 1. PANIC CLOSE LONGS
            for session_id, session in sessions.items():
                futures.append(executor.submit(self._panic_close_session, session))

            # 2. SNIPER SHORTS
            for session_id, session in sessions.items():
                for target in self.sniper_targets:
                    futures.append(executor.submit(self._sniper_short_session, session, target))

            # Wait for all
            for f in as_completed(futures):
                try:
                    f.result()
                except Exception as e:
                    logger.error(f"Defense task failed: {e}")

    def _panic_close_session(self, session):
        """Task: Close all longs for a specific session."""
        try:
            # We need a method in session to close ALL longs. 
            # Assuming get_active_positions logic.
            # Simplified: Close BTC/ETH/SOL/BNB + Current targets
            # A 'real' panic close would iterate session's known positions.
            # For robustness, we call a theoretical 'close_all_longs' or iterate main assets.
            
            # Using existing logic: Fetch active positions first
            def op():
                if not session.client: return
                positions = session.get_active_positions()
                for p in positions:
                    if float(p['positionAmt']) > 0: # Long
                        logger.info(f"Closing LONG {p['symbol']} for {session.chat_id}")
                        session.execute_close_position(p['symbol'])
            
            self.exponential_backoff(op)
            
        except Exception as e:
            logger.error(f"Panic Close Error (Session {session.chat_id}): {e}")

    def _sniper_short_session(self, session, symbol):
        """Task: Open Short for a target."""
        try:
            def op():
                # Check if already short to avoid double entry? 
                # execute_short_position has internal check (we strengthened it!)
                session.execute_short_position(symbol, atr=0) # ATR=0 implies market/default params
                
            self.exponential_backoff(op)
        except Exception as e:
            logger.error(f"Sniper Short Error ({symbol}): {e}")

    def run(self):
        logger.info("🦈 SHARK MODE SENTINEL ACTIVE (Daemon Thread)")
        
        while self.running:
            try:
                now = time.time()
                price = self.fetch_btc_price_raw()
                
                if price:
                    self.price_window.append((now, price))
                    
                    # Sliding Window Logic
                    # 1. Pop old
                    while self.price_window and self.price_window[0][0] < now - self.window_seconds:
                        self.price_window.popleft()
                    
                    if len(self.price_window) > 1:
                        start_price = self.price_window[0][1]
                        # Calc Drop
                        drop_pct = ((price - start_price) / start_price) * 100
                        
                        # LOGIC CHECK
                        if drop_pct <= -self.threshold and not self.triggered:
                            msg = f"⚠️⚠️ **SHARK MODE ACTIVATED** ⚠️⚠️\nBTC Crash detected: {drop_pct:.2f}% in {self.window_seconds}s.\n⚔️ **EJECUTANDO DEFENSA TOTAL**"
                            logger.critical(msg)
                            self.notify_callback(msg)
                            
                            self.triggered = True
                            self.execute_defense_sequence()
                            
                            # Cooldown to avoid spam loop (5 mins)
                            time.sleep(300) 
                            self.triggered = False
                            self.price_window.clear() # Reset window
                            
                # Heartbeat 1s
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"Sentinel Loop Error: {e}")
                time.sleep(5) # Prevent CPU spin on hard crash

    def stop(self):
        self.running = False
