import pandas as pd
import numpy as np

# Importar cálculos vectorizados desde indicadores (Principio DRY)
from strategies.indicators import (
    calculate_hma,
    calculate_bollinger_bands,
    calculate_keltner_channels,
    calculate_adx,
    calculate_rsi,
    calculate_adx_slope,
    calculate_ema,
    calculate_stoch_rsi,
    calculate_atr
)

class StrategyEngine:
    """
    Motor de Estrategia Financiera Modular - "Squeeze & Velocity".
    Diseñado para alta eficiencia (Vectorizado con Pandas/Numpy).
    """

    def __init__(self, data: pd.DataFrame):
        """
        Inicializa con Datos OHLCV.
        """
        self.df = data.copy()
        self.metrics = {}
        
    def calculate_indicators(self):
        """
        Calcula todos los indicadores técnicos necesarios (Spot + Futuros).
        """
        if self.df.empty:
            return

        # --- INDICADORES COMUNES & FUTUROS ---
        # 1. HMA (55)
        self.df['hma_55'] = calculate_hma(self.df['close'], period=55)
        
        # 2. Bandas de Bollinger (20, 2.0)
        bb = calculate_bollinger_bands(self.df['close'], period=20, std_dev=2.0)
        self.df['bb_upper'] = bb['upper']
        self.df['bb_lower'] = bb['lower']
        
        # 3. Canales de Keltner (20, 1.5)
        kc = calculate_keltner_channels(self.df, period=20, multiplier=1.5)
        self.df['kc_upper'] = kc['upper']
        self.df['kc_lower'] = kc['lower']
        
        # 4. ADX (14)
        adx_df = calculate_adx(self.df, period=14)
        self.df['adx'] = adx_df['adx']
        
        # 5. RSI (14)
        self.df['rsi'] = calculate_rsi(self.df['close'], period=14)
        
        # 6. ATR (14) - Para Stop Loss Dinámico
        self.df['atr'] = calculate_atr(self.df, period=14)

        # --- INDICADORES EXTRA PARA SPOT ---
        # 7. EMA (200)
        self.df['ema_200'] = calculate_ema(self.df['close'], period=200)

        # 8. StochRSI (14, 3, 3)
        stoch = calculate_stoch_rsi(self.df['rsi'], period=14, k_period=3, d_period=3)
        self.df['stoch_k'] = stoch['k']
        self.df['stoch_d'] = stoch['d']

        # 9. Volumen SMA (20)
        self.df['vol_sma'] = self.df['volume'].rolling(20).mean()

    def analyze(self) -> dict:
        """
        Ejecuta el análisis Híbrido (Spot Mean Reversion + Futures Squeeze/Velocity).
        Devuelve un diccionario unificado.
        """
        if len(self.df) < 200: # Requisito subido a 200 por EMA200
            return {
                "signal_spot": False,
                "signal_futures": "WAIT",
                "reason_spot": "",
                "reason_futures": "Datos insuficientes (< 200 velas)",
                "metrics": {}
            }

        self.calculate_indicators()
        
        curr = self.df.iloc[-1]
        prev = self.df.iloc[-2]
        
        # --- 1. ANÁLISIS SPOT (Mean Reversion) ---
        # Precio < BB Inferior Y RSI < 40 Y StochRSI Cruce Alcista en zona baja (<20)
        
        spot_signal = False
        spot_reason = ""
        
        cond_bb_spot = curr['close'] < curr['bb_lower']
        cond_rsi_spot = curr['rsi'] < 40
        cond_stoch_spot = (prev['stoch_k'] < prev['stoch_d']) and (curr['stoch_k'] > curr['stoch_d']) and (curr['stoch_k'] < 20)
        
        # Confirmación volumen (Opcional)
        vol_threshold = curr['vol_sma'] * 1.2 if pd.notna(curr['vol_sma']) else 0
        cond_vol = curr['volume'] > vol_threshold
        
        if cond_bb_spot and cond_rsi_spot and cond_stoch_spot:
            spot_signal = True
            spot_reason = "💎 **MEAN REVERSION**: Precio bajo BB + RSI bajo + Cruce StochRSI."

        # --- 2. ANÁLISIS FUTUROS (Squeeze & Velocity) ---
        
        fut_signal = "WAIT"
        fut_reason = "Monitorizando..."

        # Definiciones
        is_squeeze = (curr['bb_upper'] < curr['kc_upper']) and (curr['bb_lower'] > curr['kc_lower'])
        # Squeeze reciente (últimas 5 velas)
        recent_squeeze = any((self.df['bb_upper'].iloc[i] < self.df['kc_upper'].iloc[i]) for i in range(-5, -1))
        
        breakout_up = (curr['close'] > curr['bb_upper'])
        momentum_bullish = (curr['rsi'] > 50)
        trend_bullish = (curr['close'] > curr['hma_55'])
        adx_rising = curr['adx'] > prev['adx']
        adx_strong = curr['adx'] > 20
        
        # Lógica de Entrada (LONG)
        if breakout_up and trend_bullish and momentum_bullish and adx_rising:
            if recent_squeeze:
                fut_signal = "BUY"
                fut_reason = "🚀 **SQUEEZE BREAKOUT**: Ruptura tras compresión."
            elif adx_strong:
                fut_signal = "BUY"
                fut_reason = "🌊 **TREND VELOCITY**: Continuación de tendencia fuerte."

        # Lógica de Entrada (SHORT)
        # Inverse logic: Breakout Down, Price < HMA, RSI < 50
        breakout_down = (curr['close'] < curr['bb_lower'])
        momentum_bearish = (curr['rsi'] < 50)
        trend_bearish = (curr['close'] < curr['hma_55'])
        
        if breakout_down and trend_bearish and momentum_bearish and adx_rising:
             # Prioritizes Shorts if we are not already in Long logic (which we aren't if fut_signal is WAIT)
             if fut_signal == "WAIT":
                if recent_squeeze:
                    fut_signal = "SHORT"
                    fut_reason = "🔻 **SQUEEZE SHORT**: Ruptura bajista tras compresión."
                elif adx_strong:
                    fut_signal = "SHORT"
                    fut_reason = "📉 **BEARISH VELOCITY**: Tendencia bajista fuerte."
        
        # Lógica de Salida (Close Long / Close Short)
        adx_collapse = (prev['adx'] > 30 and curr['adx'] < 25)
        trend_loss_bull = (curr['close'] < curr['hma_55'])
        trend_loss_bear = (curr['close'] > curr['hma_55'])
        
        # Determine Exit based on assumed state (Caller handles state, here we return generic close signals depending on chart violation)
        # Actually, best practice is to return specific "CLOSE_LONG" or "CLOSE_SHORT" if we detect that specific violation.
        # But since we don't know the state here, we can flag both? 
        # Better approach: Return distinct signals. The Loop checks state.
        
        if trend_loss_bull:
            # Crucial for Longs to close
            if fut_signal == "WAIT": fut_signal = "CLOSE_LONG"
            fut_reason = "📉 **TENDENCIA ROTA**: Precio bajo HMA 55."
            
        elif trend_loss_bear:
            # Crucial for Shorts to close
            if fut_signal == "WAIT": fut_signal = "CLOSE_SHORT"
            fut_reason = "📈 **RECUPERACIÓN**: Precio sobre HMA 55."
            
        elif adx_collapse:
             # Valid for both
             if fut_signal == "WAIT": fut_signal = "EXIT_ALL" # Generic Exit
             fut_reason = "exhaustion **ADX**: Pérdida de fuerza (Side)."

        # --- MÉTRICAS FINALES ---
        final_metrics = {
            "close": float(curr['close']),
            "rsi": float(curr['rsi']),
            "adx": float(curr['adx']),
            "squeeze_on": bool(is_squeeze or recent_squeeze),
            "stoch_k": float(curr['stoch_k']),
            "bb_lower": float(curr['bb_lower']),
            "hma_55": float(curr['hma_55']),
            "atr": float(curr['atr'])
        }

        return {
            "signal_spot": spot_signal,
            "signal_futures": fut_signal,
            "reason_spot": spot_reason,
            "reason_futures": fut_reason,
            "metrics": final_metrics
        }
