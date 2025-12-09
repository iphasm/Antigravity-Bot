import pandas as pd
import numpy as np

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculates the Relative Strength Index (RSI).
    Uses Wilder's smoothing (alpha = 1/period) via ewm(com=period-1).
    """
    delta = series.diff()
    
    # Separate gains and losses
    gain = (delta.where(delta > 0, 0)).fillna(0)
    loss = (-delta.where(delta < 0, 0)).fillna(0) # Store as positive values

    # Wilder's Smoothing
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()

    # Calculate RS
    rs = avg_gain / avg_loss
    
    # Calculate RSI: 100 - (100 / (1 + RS))
    rsi = 100 - (100 / (1 + rs))
    
    # Handle division by zero (avg_loss == 0 means RSI is 100)
    rsi = rsi.replace([np.inf], 100)
    
    # Handle NaN at start
    rsi = rsi.fillna(0)
    
    return rsi

def calculate_stoch_rsi(rsi_series: pd.Series, period: int = 14, k_period: int = 3, d_period: int = 3) -> pd.DataFrame:
    """
    Calculates the Stochastic RSI.
    Input: RSI Series (not price).
    Formula: (rsi - min_rsi) / (max_rsi - min_rsi)
    Returns values in 0-100 range (multiplied by 100).
    Returns DataFrame with 'k' (smoothed StochRSI) and 'd' (SMA of k).
    """
    # Calculate Min/Max RSI in window
    min_rsi = rsi_series.rolling(window=period).min()
    max_rsi = rsi_series.rolling(window=period).max()
    
    # Calculate Stoch RSI (Fast %K)
    # Avoid division by zero
    denominator = max_rsi - min_rsi
    stoch_rsi = (rsi_series - min_rsi) / denominator
    
    # Handle NaNs from calculation (0/0 etc)
    stoch_rsi = stoch_rsi.fillna(0)
    
    # Scale to 0-100 as per common oscillators for consistency
    stoch_rsi_100 = stoch_rsi * 100
    
    # Smooth %K
    k_line = stoch_rsi_100.rolling(window=k_period).mean()
    
    # Calculate %D (SMA of %K)
    d_line = k_line.rolling(window=d_period).mean()
    
    # Handle NaNs
    k_line = k_line.fillna(0)
    d_line = d_line.fillna(0)
    
    return pd.DataFrame({'k': k_line, 'd': d_line})

def calculate_macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    """
    Calculates MACD, Signal line, and Histogram.
    """
    # EMA Fast
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    
    # EMA Slow
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    
    # MACD Line
    macd_line = ema_fast - ema_slow
    
    # Signal Line
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    
    # Histogram
    histogram = macd_line - signal_line
    
    # Handle NaNs
    macd_line = macd_line.fillna(0)
    signal_line = signal_line.fillna(0)
    histogram = histogram.fillna(0)
    
    return pd.DataFrame({
        'macd': macd_line,
        'signal': signal_line,
        'histogram': histogram
    })

def calculate_bollinger_bands(series: pd.Series, period: int = 20, std_dev: int = 2) -> pd.DataFrame:
    """
    Calculates Bollinger Bands (Upper, Middle, Lower).
    """
    # Middle Band: SMA
    middle = series.rolling(window=period).mean()
    
    # Standard Deviation
    std = series.rolling(window=period).std()
    
    # Upper/Lower Bands
    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)
    
    # Handle NaNs (e.g. initial rolling window)
    middle = middle.bfill().fillna(0)
    upper = upper.bfill().fillna(0)
    lower = lower.bfill().fillna(0)
    
    return pd.DataFrame({
        'upper': upper,
        'middle': middle,
        'lower': lower
    })

def calculate_ema(series: pd.Series, period: int = 200) -> pd.Series:
    """
    Calculates Exponential Moving Average (EMA).
    """
    return series.ewm(span=period, adjust=False).mean()

def calculate_wma(series: pd.Series, period: int) -> pd.Series:
    """
    Calculates Weighted Moving Average (WMA).
    weights: [1, 2, ..., period]
    """
    return series.rolling(period).apply(lambda x: ((x * np.arange(1, period + 1)).sum()) / (np.arange(1, period + 1).sum()), raw=True)

def calculate_hma(series: pd.Series, period: int = 55) -> pd.Series:
    """
    Calculates Hull Moving Average (HMA).
    Formula: WMA(2 * WMA(n/2) - WMA(n), sqrt(n))
    """
    half_period = int(period / 2)
    sqrt_period = int(np.sqrt(period))
    
    wma_half = calculate_wma(series, half_period)
    wma_full = calculate_wma(series, period)
    
    raw_hma = (2 * wma_half) - wma_full
    hma = calculate_wma(raw_hma, sqrt_period)
    return hma

def calculate_adx(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
    """
    Calculates ADX, DI+, DI-.
    Returns DataFrame with columns: ['adx', 'plus_di', 'minus_di']
    """
    # 1. True Range
    high = df['high']
    low = df['low']
    close = df['close']
    
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # 2. Directional Movement
    up_move = high - high.shift(1)
    down_move = low.shift(1) - low
    
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    
    # 3. Smoothed TR and DM (Wilder's Smoothing)
    # Note: ewm(alpha=1/period) is equivalent to Wilder's
    alpha = 1 / period
    
    tr_smooth = tr.ewm(alpha=alpha, adjust=False).mean()
    plus_dm_smooth = pd.Series(plus_dm, index=df.index).ewm(alpha=alpha, adjust=False).mean()
    minus_dm_smooth = pd.Series(minus_dm, index=df.index).ewm(alpha=alpha, adjust=False).mean()
    
    # 4. DI+ and DI-
    plus_di = 100 * (plus_dm_smooth / tr_smooth)
    minus_di = 100 * (minus_dm_smooth / tr_smooth)
    
    # 5. DX
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    
    # 6. ADX (Smoothed DX)
    # Standard ADX uses the same smoothing on DX
    adx = dx.ewm(alpha=alpha, adjust=False).mean()
    
    return pd.DataFrame({
        'adx': adx,
        'plus_di': plus_di,
        'minus_di': minus_di
    }).fillna(0)

def calculate_adx_slope(adx_series: pd.Series) -> pd.Series:
    """
    Returns boolean series: True if ADX is rising (current > prev).
    """
    return adx_series > adx_series.shift(1)
