import pandas as pd
from strategies.indicators import (
    calculate_rsi,
    calculate_stoch_rsi,
    calculate_bollinger_bands,
    calculate_ema,
    calculate_hma,
    calculate_adx,
    calculate_adx_slope
)

def check_trend_velocity(df: pd.DataFrame) -> tuple[bool, dict]:
    """
    BTC Trend Velocity Strategy.
    
    Long Signal:
    1. Close > HMA(55)
    2. DI+ > DI-
    3. ADX > 20
    4. ADX Rising
    5. RSI > 50
    """
    try:
        # Calculate Indicators
        df['hma_55'] = calculate_hma(df['close'], period=55)
        
        adx_df = calculate_adx(df, period=14)
        df['adx'] = adx_df['adx']
        df['plus_di'] = adx_df['plus_di']
        df['minus_di'] = adx_df['minus_di']
        
        df['adx_rising'] = calculate_adx_slope(df['adx'])
        
        # RSI already calculated in main analyzer if called from there, but calc here to be safe/standalone
        if 'rsi' not in df.columns:
            df['rsi'] = calculate_rsi(df['close'], period=14)
            
        curr = df.iloc[-1]
        
        # Conditions
        # 1. Trend Filter
        c_trend = curr['close'] > curr['hma_55']
        
        # 2. Direction
        c_direction = curr['plus_di'] > curr['minus_di']
        
        # 3. Strength
        c_strength = curr['adx'] > 20
        c_rising = bool(curr['adx_rising'])
        
        # 4. Momentum
        c_momentum = curr['rsi'] > 50
        
        # Final Signal
        long_signal = c_trend and c_direction and c_strength and c_rising and c_momentum
        
        debug_info = {
            'tv_trend_hma': bool(c_trend),
            'tv_dir_plus': bool(c_direction),
            'tv_str_adx': bool(c_strength),
            'tv_adx_rise': bool(c_rising),
            'tv_mom_rsi': bool(c_momentum)
        }
        
        return long_signal, debug_info
        
    except Exception as e:
        print(f"Error in Trend Velocity: {e}")
        return False, {"error": str(e)}

def analyze_market(df: pd.DataFrame) -> tuple[bool, dict]:
    """
    Combined Strategy:
    1. Mean Reversion (Existing)
    OR
    2. BTC Trend Velocity (New)
    """
    # 0. Data Validation
    if df.empty or len(df) < 200:
        return False, {"error": "Insufficient data (needs >200 candles)"}

    try:
        # --- STRATEGY 1: Mean Reversion ---
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
        stoch = calculate_stoch_rsi(df['rsi'], period=14, k_period=3, d_period=3)
        df['stoch_k'] = stoch['k']
        df['stoch_d'] = stoch['d']
        
        # Evaluate Mean Reversion
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        cond_setup = curr['close'] < curr['bb_lower']
        cond_trend = curr['close'] > curr['ema_200'] # Mean reversion logic prefers uptrend pullback
        vol_avg = curr['vol_sma_20'] if pd.notna(curr['vol_sma_20']) else 0
        cond_volume = curr['volume'] > (vol_avg * 1.5)
        cross_up = (prev['stoch_k'] < prev['stoch_d']) and (curr['stoch_k'] > curr['stoch_d'])
        in_zone = curr['stoch_k'] < 20
        cond_trigger = cross_up and in_zone
        
        signal_mean_rev = cond_setup and cond_trend and cond_volume and cond_trigger
        
        # --- STRATEGY 2: Trend Velocity ---
        signal_trend_vel, tv_debug = check_trend_velocity(df)
        
        # --- COMBINED SIGNAL (OR Logic) ---
        final_buy_signal = signal_mean_rev or signal_trend_vel
        
        # Metrics Construction
        metric_vol_ratio = round(curr['volume'] / vol_avg, 2) if vol_avg > 0 else 0
        
        metrics_dict = {
            'close': float(curr['close']),
            'rsi': float(curr['rsi']),
            'stoch_k': float(curr['stoch_k']),
            'stoch_d': float(curr['stoch_d']),
            'bb_lower': float(curr['bb_lower']),
            'ema_200': float(curr['ema_200']),
            'hma_55': float(df.iloc[-1].get('hma_55', 0)),
            'adx': float(df.iloc[-1].get('adx', 0)),
            'vol_ratio': metric_vol_ratio,
            'source': 'TrendVelocity' if signal_trend_vel else ('MeanReversion' if signal_mean_rev else 'None'),
             'debug': {
                'mr_setup': bool(cond_setup),
                'mr_trigger': bool(cond_trigger),
                **tv_debug
            }
        }
        
        return final_buy_signal, metrics_dict

    except Exception as e:
        print(f"❌ Analysis Error: {e}")
        import traceback
        traceback.print_exc()
        return False, {"error": str(e)}

