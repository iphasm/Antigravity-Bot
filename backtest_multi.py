import pandas as pd
import numpy as np
import json
import os
from data.fetcher import get_market_data
from strategies.engine import StrategyEngine
import time

def run_backtest(symbol, timeframe='15m', limit=1000):
    print(f"⏳ Fetching data for {symbol}...")
    try:
        df = get_market_data(symbol, timeframe=timeframe, limit=limit)
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return pd.DataFrame(), []

    if df.empty:
        print(f"⚠️ No data found for {symbol}")
        return pd.DataFrame(), []

    # Initialize Engine to calculate indicators
    engine = StrategyEngine(df)
    engine.calculate_indicators()
    df = engine.df

    # Backtest Logic (Replicating StrategyEngine.analyze logic for historical data)
    markers = []
    
    # Ensure index is accessible for timestamp
    if 'timestamp' in df.columns:
        times = df['timestamp']
    else:
        times = df.index

    # Shifted/Rolling calculations for conditions that look at previous candles
    # Ideally, we should loop or use vectorized shift.
    # For clarity and matching the engine exactly, we'll iterate efficiently.
    # We need at least index 200 (for EMA200) or whatever start point.
    
    start_idx = 200
    
    # Pre-calculate conditions to speed up loop? Or just loop. 1000 rows is nothing.
    for i in range(start_idx, len(df)):
        curr = df.iloc[i]
        prev = df.iloc[i-1]
        
        # --- FUTURES STRATEGY LOGIC COPY ---
        # Definitions matching engine.py
        is_squeeze = (curr['bb_upper'] < curr['kc_upper']) and (curr['bb_lower'] > curr['kc_lower'])
        
        # Recent squeeze (last 5 candles) - This is a bit tricky to look back efficiently in a loop
        # We can look at the slice [i-5 : i-1]
        recent_squeeze = False
        if i >= 5:
            subset = df.iloc[i-5:i]
            # check if any candle in subset had squeeze
            squeeze_check = (subset['bb_upper'] < subset['kc_upper']) & (subset['bb_lower'] > subset['kc_lower'])
            recent_squeeze = squeeze_check.any()

        breakout_up = (curr['close'] > curr['bb_upper'])
        momentum_bullish = (curr['rsi'] > 50)
        trend_bullish = (curr['close'] > curr['hma_55'])
        adx_rising = curr['adx'] > prev['adx']
        adx_strong = curr['adx'] > 20
        
        signal = None
        text = ""

        # Entry Logic
        if breakout_up and trend_bullish and momentum_bullish and adx_rising:
            if recent_squeeze:
                signal = 'buy'
                text = 'Sqze Break'
            elif adx_strong:
                signal = 'buy'
                text = 'Velo Break'
        
        # Exit Logic (Close Long)
        adx_collapse = (prev['adx'] > 30 and curr['adx'] < 25)
        trend_loss = (curr['close'] < curr['hma_55'])
        
        if trend_loss:
            signal = 'sell' # Close Long
            text = 'Trend Loss'
        elif adx_collapse:
            signal = 'sell' # Close Long
            text = 'ADX Exhaust'

        if signal:
            # Timestamp to Unix Seconds
            ts = int(pd.Timestamp(times[i]).timestamp())
            
            color = '#2196F3' if signal == 'buy' else '#E91E63'
            shape = 'arrowUp' if signal == 'buy' else 'arrowDown'
            position = 'belowBar' if signal == 'buy' else 'aboveBar'
            
            markers.append({
                'time': ts,
                'position': position,
                'color': color,
                'shape': shape,
                'text': text
            })

    return df, markers

def generate_multi_chart():
    # 1. Backtest BTC
    df_btc, markers_btc = run_backtest('BTCUSDT', limit=1000)
    
    # 2. Backtest Gold
    df_gold, markers_gold = run_backtest('GC=F', limit=1000) # Gold Futures

    # Prepare Data for Charting
    def prepare_ohlc_hma(df):
        ohlc = []
        hma = []
        if df.empty: return [], []
        
        if 'timestamp' in df.columns:
            ts_col = df['timestamp']
        else:
            ts_col = df.index
            
        for i in range(len(df)):
            ts = int(pd.Timestamp(ts_col[i]).timestamp())
            ohlc.append({
                'time': ts,
                'open': float(df.iloc[i]['open']),
                'high': float(df.iloc[i]['high']),
                'low': float(df.iloc[i]['low']),
                'close': float(df.iloc[i]['close']),
            })
            if not pd.isna(df.iloc[i]['hma_55']):
                hma.append({
                    'time': ts,
                    'value': float(df.iloc[i]['hma_55'])
                })
        return ohlc, hma

    ohlc_btc, hma_btc = prepare_ohlc_hma(df_btc)
    ohlc_gold, hma_gold = prepare_ohlc_hma(df_gold)

    # HTML Content
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Backtest Strategy: BTC & Gold</title>
        <meta charset="utf-8" />
        <script src="https://unpkg.com/lightweight-charts@4.1.1/dist/lightweight-charts.standalone.production.js"></script>
        <style>
            body {{ margin: 0; padding: 20px; background-color: #121212; font-family: 'Segoe UI', sans-serif; color: #e0e0e0; }}
            .chart-container {{ position: relative; width: 100%; height: 400px; margin-bottom: 30px; border: 1px solid #333; }}
            h2 {{ margin: 0 0 10px 0; color: #f0f0f0; }}
            .legend {{ position: absolute; left: 12px; top: 12px; z-index: 1; font-size: 14px; background: rgba(0,0,0,0.5); padding: 5px; border-radius: 4px;}}
        </style>
    </head>
    <body>
        <h2>Bitcoin (BTCUSDT) - Futures Strategy</h2>
        <div id="chart_btc" class="chart-container"></div>
        
        <h2>Gold (GC=F) - Futures Strategy</h2>
        <div id="chart_gold" class="chart-container"></div>

        <script>
            function createChart(id, ohlcData, markersData, hmaData) {{
                const chart = LightweightCharts.createChart(document.getElementById(id), {{
                    layout: {{ textColor: '#d1d4dc', background: {{ type: 'solid', color: '#121212' }} }},
                    grid: {{ vertLines: {{ color: '#2B2B43' }}, horzLines: {{ color: '#2B2B43' }} }},
                    timeScale: {{ timeVisible: true, borderColor: '#485c7b' }},
                }});

                const series = chart.addCandlestickSeries({{
                    upColor: '#26a69a', downColor: '#ef5350', borderVisible: false, wickUpColor: '#26a69a', wickDownColor: '#ef5350'
                }});
                series.setData(ohlcData);
                series.setMarkers(markersData);

                const hmaSeries = chart.addLineSeries({{ color: '#FF9800', lineWidth: 2, priceLineVisible: false }});
                hmaSeries.setData(hmaData);

                chart.timeScale().fitContent();
                
                new ResizeObserver(entries => {{
                    if (entries.length === 0 ||entries[0].target !== document.getElementById(id)) {{ return; }}
                    const newRect = entries[0].contentRect;
                    chart.applyOptions({{ height: newRect.height, width: newRect.width }});
                }}).observe(document.getElementById(id));
                
                return chart;
            }}

            const btcData = {json.dumps(ohlc_btc)};
            const btcMarkers = {json.dumps(markers_btc)};
            const btcHma = {json.dumps(hma_btc)};

            const goldData = {json.dumps(ohlc_gold)};
            const goldMarkers = {json.dumps(markers_gold)};
            const goldHma = {json.dumps(hma_gold)};

            createChart('chart_btc', btcData, btcMarkers, btcHma);
            createChart('chart_gold', goldData, goldMarkers, goldHma);
        </script>
    </body>
    </html>
    """
    
    output_path = r"c:\Users\iphas\OneDrive\Documents\GitHub\Antigravity-Bot\btc_gold_strategy.html"
    with open(output_path, "w", encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"✅ Multi-chart generated at: {output_path}")

if __name__ == "__main__":
    generate_multi_chart()
