import pandas as pd
import numpy as np
from strategies.analyzer import check_trend_velocity, analyze_market
from strategies.indicators import calculate_hma, calculate_adx

def generate_trend_velocity_data(length=200):
    """
    Generates data that should technically trigger the Trend Velocity strategy.
    
    Conditions for Buy:
    1. Close > HMA(55)
    2. DI+ > DI-
    3. ADX > 20
    4. ADX Rising
    5. RSI > 50
    """
    index = pd.date_range(start='2023-01-01', periods=length, freq='15min')
    
    half = int(length / 2)
    
    # Segment 1: CHOP (Flat price, high noise) -> Low ADX
    # Price stays around 100
    p1 = np.ones(half) * 100
    # Add noise
    noise1 = np.random.normal(0, 2, half)
    c1 = p1 + noise1
    h1 = c1 + 2
    l1 = c1 - 2
    
    # Segment 2: TREND (Rising price) -> Rising ADX
    # Price goes 100 -> 150
    p2 = np.linspace(100, 150, length - half)
    # No noise to ensure rising ADX is deterministic
    c2 = p2 
    # Expanding range to help ADX rise
    ranges = np.linspace(2, 5, length - half)
    h2 = c2 + ranges
    l2 = c2 - ranges
    
    # Concatenate
    close = np.concatenate([c1, c2])
    high = np.concatenate([h1, h2])
    low = np.concatenate([l1, l2])
    volume = np.random.normal(100, 10, length)
    
    df = pd.DataFrame({
        'open': close,
        'high': high,
        'low': low,
        'close': close,
        'volume': volume
    }, index=index)
    
    return df

def test_hma():
    print("\n--- Testing HMA ---")
    data = pd.Series(np.linspace(10, 100, 100))
    hma = calculate_hma(data, 55)
    print(f"HMA (Last): {hma.iloc[-1]:.2f}")
    if abs(hma.iloc[-1] - 100) < 5:
        print("✅ HMA tracking linear trend correctly")
    else:
        print(f"❌ HMA deviation too high: {hma.iloc[-1]}")

def test_adx():
    print("\n--- Testing ADX Trajectory ---")
    df = generate_trend_velocity_data(100)
    adx_df = calculate_adx(df, 14)
    
    print("Last 5 ADX values:")
    print(adx_df['adx'].tail(5))
    
    last_adx = adx_df['adx'].iloc[-1]
    prev_adx = adx_df['adx'].iloc[-2]
    
    print(f"Rising? {last_adx:.4f} > {prev_adx:.4f} = {last_adx > prev_adx}")
    
    if last_adx > prev_adx:
        print("✅ ADX is rising")
    else:
        print("❌ ADX is NOT rising")

def test_full_strategy():
    print("\n--- Testing Full Trend Velocity Logic ---")
    df = generate_trend_velocity_data(300)
    
    # Run Check
    is_buy, debug = check_trend_velocity(df)
    
    print(f"Buy Signal: {is_buy}")
    print("Debug:", debug)
    
    if is_buy:
        print("✅ Strategy triggered on synthetic uptrend data")
    else:
        print("⚠️ Strategy NOT triggered (Check debug output)")

    # Run Integrated Analyzer
    print("\n--- Testing Integrated Analyzer ---")
    final_signal, metrics = analyze_market(df)
    print(f"Combined Signal: {final_signal}")
    print(f"Source: {metrics.get('source')}")
    
    if final_signal and metrics.get('source') == 'TrendVelocity':
        print("✅ Integrated Analyzer correctly identified TrendVelocity signal")
    else:
        print("❌ Integrated Analyzer failed to identify signal")

if __name__ == "__main__":
    try:
        test_hma()
        test_adx()
        test_full_strategy()
    except Exception as e:
        print(f"\n❌ Test Failed: {e}")
        import traceback
        traceback.print_exc()
