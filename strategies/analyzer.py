import pandas as pd
from strategies.indicators import (
    calculate_rsi,
    calculate_stoch_rsi,
    calculate_bollinger_bands,
    calculate_ema
)

def analyze_market(df: pd.DataFrame) -> tuple[bool, dict]:
    """
    Advanced Strategy: Mean Reversion with Trend & Volume Confirmation.
    (Implemented with standard Pandas due to Python 3.14 compatibility)
    
    Logic (AND):
    1. Setup: Close < BB_Lower (Oversold outlier)
    2. Trend: Close > EMA_200 (Overlapping pullback in up-trend)
    3. Volume: Volume > 1.5 * Volume_SMA_20 (Climax confirmation)
    4. Trigger: StochRSI Bullish Crossover in Oversold (<20)
    """
    # 0. Data Validation
    if df.empty or len(df) < 200:
        return False, {"error": "Insufficient data (needs >200 candles)"}

    try:
        # --- 1. CALCULATE INDICATORS ---
        
        # A. EMA 200
        df['ema_200'] = calculate_ema(df['close'], period=200)
        
        # B. Bollinger Bands (20, 2)
        bb = calculate_bollinger_bands(df['close'], period=20, std_dev=2)
        df['bb_lower'] = bb['lower']
        
        # C. Volume SMA 20
        df['vol_sma_20'] = df['volume'].rolling(window=20).mean()
        
        # D. RSI 14
        df['rsi'] = calculate_rsi(df['close'], period=14)
        
        # E. StochRSI (14, 3, 3)
        # Note: Our calculate_stoch_rsi expects RSI series input
        stoch = calculate_stoch_rsi(df['rsi'], period=14, k_period=3, d_period=3)
        df['stoch_k'] = stoch['k']
        df['stoch_d'] = stoch['d']
        
        # --- 2. EVALUATE CONDITIONS ---
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Condition 1: Setup (Close < BB Lower)
        cond_setup = curr['close'] < curr['bb_lower']
        
        # Condition 2: Trend (Close > EMA 200)
        cond_trend = curr['close'] > curr['ema_200']
        
        # Condition 3: Volume Climax
        # Handle nan volume sma
        vol_avg = curr['vol_sma_20'] if pd.notna(curr['vol_sma_20']) else 0
        cond_volume = curr['volume'] > (vol_avg * 1.5)
        
        # Condition 4: Trigger (Stoch Cross Up in Oversold)
        cross_up = (prev['stoch_k'] < prev['stoch_d']) and (curr['stoch_k'] > curr['stoch_d'])
        in_zone = curr['stoch_k'] < 20
        cond_trigger = cross_up and in_zone
        
        # --- 3. FINAL SIGNAL ---
        buy_signal = cond_setup and cond_trend and cond_volume and cond_trigger
        
        metric_vol_ratio = round(curr['volume'] / vol_avg, 2) if vol_avg > 0 else 0
        
        metrics_dict = {
            'close': float(curr['close']),
            'rsi': float(curr['rsi']),
            'stoch_k': float(curr['stoch_k']),
            'stoch_d': float(curr['stoch_d']),
            'bb_lower': float(curr['bb_lower']),
            'ema_200': float(curr['ema_200']),
            'vol_ratio': metric_vol_ratio,
             'debug': {
                'setup_bb': bool(cond_setup),
                'trend_ema': bool(cond_trend),
                'vol_climax': bool(cond_volume),
                'trigger_stoch': bool(cond_trigger)
            }
        }
        
        return buy_signal, metrics_dict

    except Exception as e:
        print(f"❌ Analysis Error: {e}")
        import traceback
        traceback.print_exc()
        return False, {"error": str(e)}

