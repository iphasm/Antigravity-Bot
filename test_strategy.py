import pandas as pd
import numpy as np
from strategies.analyzer import analyze_market

def generate_dummy_data(length=300):
    """Generates a dummy DataFrame with sufficient length for EMA200"""
    dates = pd.date_range(start='2023-01-01', periods=length, freq='15min')
    
    # Random walk for Close
    close = [100.0]
    for _ in range(length-1):
        change = np.random.normal(0, 1)
        close.append(close[-1] + change)
        
    # Volume: mostly 100, one spike at end
    volume = [100.0] * length
    volume[-1] = 500.0 # Spike
    
    df = pd.DataFrame({
        'timestamp': dates,
        'open': close,
        'high': close,
        'low': close,
        'close': close,
        'volume': volume
    })
    return df

def test_strategy():
    print("TEST: Generating Dummy Data (300 candles)...")
    df = generate_dummy_data(300)
    
    print("TEST: Running analyze_market...")
    signal, metrics = analyze_market(df)
    
    print(f"Signal: {signal}")
    print("Metrics Keys:", metrics.keys())
    
    if 'error' in metrics:
        print(f"❌ Error in metrics: {metrics['error']}")
        raise Exception("Analysis failed")
    
    required_keys = ['close', 'rsi', 'stoch_k', 'stoch_d', 'bb_lower', 'ema_200', 'vol_ratio', 'debug']
    for k in required_keys:
        if k not in metrics:
            print(f"❌ Missing key: {k}")
            raise Exception(f"Missing key {k}")
            
    print("✅ Logic executed. Metrics structure valid.")
    print("Debug Info:", metrics.get('debug'))

if __name__ == "__main__":
    test_strategy()
