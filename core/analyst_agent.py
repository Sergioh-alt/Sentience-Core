"""
EEA-2026-ANT: core/analyst_agent.py
Analista SOTA — Extrae señales puras de datos crudos.
FIX-M2: Sistema de scoring en vez de 3 condiciones AND imposibles.
Migrado a ProviderPool centralizado.
"""
import json
import time
import logging
import pandas_ta as ta

from core.provider_pool import ProviderPool

log = logging.getLogger("EEA-2026")


class AnalystAgent:
    def __init__(self, aid="Analyst-Main"):
        self.aid = aid

        # Memoria caché de corto plazo para evitar quemar APIs
        self.memory_cache = {}
        self.CACHE_LIFETIME = 300  # 5 minutos de validez
        self.RSI_TOLERANCE = 2.0   # Si RSI no se mueve >2 puntos, usar caché

    def analyze_opportunity(self, ticker, df, social_data, fg_value):
        if df is None or len(df) < 20:
            return json.dumps({"decision": "HOLD", "reason": "Data insuficiente"})

        # Cálculo de indicadores técnicos
        df['RSI_14'] = ta.rsi(df['Close'], length=14)
        macd = ta.macd(df['Close'])
        df['MACD'] = macd['MACD_12_26_9']
        df['MACD_Signal'] = macd['MACDs_12_26_9']
        bb = ta.bbands(df['Close'], length=20)
        # Los nombres de columna pueden variar entre versiones de pandas_ta
        try:
            bb_lower_col = [c for c in bb.columns if 'BBL' in c][0]
            bb_upper_col = [c for c in bb.columns if 'BBU' in c][0]
            df['BB_Lower'] = bb[bb_lower_col]
            df['BB_Upper'] = bb[bb_upper_col]
        except (IndexError, TypeError):
            df['BB_Lower'] = df['Close'] * 0.98  # Fallback: 2% debajo
            df['BB_Upper'] = df['Close'] * 1.02  # Fallback: 2% arriba
        df.fillna(0, inplace=True)

        current_price = df.iloc[-1]['Close']
        current_rsi = df.iloc[-1]['RSI_14']
        current_macd = df.iloc[-1]['MACD']
        current_macd_signal = df.iloc[-1]['MACD_Signal']
        current_bb_lower = df.iloc[-1]['BB_Lower']
        current_bb_upper = df.iloc[-1]['BB_Upper']
        score = social_data.get("score", 0.5)

        # ============================================================
        # FIX-M2: SISTEMA DE SCORING
        # El bug original: exigía RSI<45 AND score>0.6 AND precio<=BB_lower
        # simultáneamente, lo que casi nunca ocurre (condiciones contradictorias).
        # Ahora usamos un sistema de scoring donde 2 de 4 señales = BUY.
        # ============================================================
        buy_score = 0
        sell_score = 0

        # Señales de compra
        if current_rsi < 45:
            buy_score += 1      # RSI en zona baja
        if score > 0.6:
            buy_score += 1      # Hype social positivo
        if current_price <= current_bb_lower * 1.02:  # 2% de tolerancia sobre BB
            buy_score += 1      # Precio cerca de Bollinger inferior
        if current_macd > current_macd_signal:
            buy_score += 1      # Cruce MACD alcista

        # Señales de venta
        if current_rsi > 70:
            sell_score += 1
        if current_price >= current_bb_upper * 0.98:  # 2% de tolerancia
            sell_score += 1
        if current_macd < current_macd_signal and current_rsi > 55:
            sell_score += 1

        decision_matematica = "HOLD"
        if buy_score >= 2 and sell_score == 0:
            decision_matematica = "BUY"
        elif sell_score >= 2:
            decision_matematica = "SELL"

        # Caché semántico: evita quemar APIs si nada cambió
        now = time.time()
        if ticker in self.memory_cache:
            cached = self.memory_cache[ticker]
            if ((now - cached['time'] < self.CACHE_LIFETIME) and
                    (abs(current_rsi - cached['rsi']) < self.RSI_TOLERANCE)):
                log.info(f"[{self.aid}] [CACHE] Usando Cache para {ticker} (Latencia 0ms)")
                return json.dumps({
                    "decision": cached['decision'],
                    "reason": f"[CACHÉ] {cached['reason']}"
                })

        # ============================================================
        # VELOCIDAD SOTA: Decisiones 100% locales (0ms)
        # ============================================================
        reason = f"Latencia 0ms | RSI={current_rsi:.1f} MACD={'Alcista' if current_macd > current_macd_signal else 'Bajista'} | Buy:{buy_score}/4"
        
        # Guardar en caché
        now = time.time()
        self.memory_cache[ticker] = {
            'time': now, 'rsi': current_rsi,
            'decision': decision_matematica, 'reason': reason
        }
        
        return json.dumps({
            "decision": decision_matematica,
            "reason": reason
        })