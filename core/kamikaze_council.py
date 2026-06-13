"""
EEA-2026-ANT: core/kamikaze_council.py
Consejo Kamikaze — Consejo AGRESIVO separado del conservador.
DIFERENCIAS vs AnalystAgent (conservador):
- Compra en momentum (RSI > 55 en vez de RSI < 45)
- Take profit más rápido (8% en vez de 15%)
- No necesita 2 votos (la moneda #1 más volátil pasa directo)
- Presupuesto diario fijo ($15/día) que se resetea cada día
- Usa hype social como acelerador
- Bloquea en euforia extrema (F&G > 75)
FIX-M1: SELL antes de BUY en evaluación RSI.
FIX-MATH: score >= 0.5 (era > 0.5, el default es 0.5 así que nunca pasaba).
"""
import json
import logging
import pandas_ta as ta
from datetime import datetime
from core.provider_pool import ProviderPool
from core.constitution import AIConstitution

log = logging.getLogger("EEA-2026")


class KamikazeCouncil:
    def __init__(self, aid="Kamikaze-Squad"):
        self.aid = aid
        self.daily_budget = 15.00     # Presupuesto diario fijo (separado del conservador)
        self.spent_today = 0.00
        self.last_reset_date = datetime.now().date()
        self.take_profit_pct = 0.08   # 8% take profit (más agresivo que el 15% conservador)
        self.trades_today = 0
        self.max_daily_trades = 5     # Más trades que el conservador (3)
        self.constitution = AIConstitution()

    def _check_budget_reset(self):
        """Resetea el presupuesto cada día a medianoche."""
        today = datetime.now().date()
        if today > self.last_reset_date:
            log.info(f"[{self.aid}] 🔄 Nuevo día — Presupuesto reseteado a ${self.daily_budget}")
            self.spent_today = 0.00
            self.trades_today = 0
            self.last_reset_date = today

    def register_expense(self, amount):
        """Registra cuánto se gastó del presupuesto diario."""
        self.spent_today += amount
        self.trades_today += 1
        remaining = self.daily_budget - self.spent_today
        log.info(f"[{self.aid}] 💰 Gastado: ${amount:.2f} | Restante hoy: ${remaining:.2f}")

    def get_budget_status(self):
        """Retorna el estado del presupuesto para el HUD."""
        self._check_budget_reset()
        return {
            "budget": self.daily_budget,
            "spent": round(self.spent_today, 2),
            "remaining": round(self.daily_budget - self.spent_today, 2),
            "trades_today": self.trades_today,
            "max_trades": self.max_daily_trades
        }

    def analyze_volatile_asset(self, ticker, df, social_data, fg_value=50):
        """
        Análisis agresivo para la moneda más volátil del screener.
        """
        self._check_budget_reset()

        # Validación Constitucional (Fase Autónoma)
        rsi_now = float(df.iloc[-1]['RSI_14']) if df is not None and 'RSI_14' in df.columns else 50
        indicators = {"rsi": rsi_now, "exposure": self.spent_today / 100}
        is_legal, const_reason = self.constitution.validate_proposal(ticker, indicators)
        if not is_legal:
            return json.dumps({"decision": "HOLD", "reason": f"BLOQUEO_CONSTITUCIONAL: {const_reason}"})

        # Bloqueo 1: Presupuesto agotado
        if self.spent_today >= self.daily_budget:
            return json.dumps({"decision": "HOLD", "reason": "Presupuesto Kamikaze agotado."})

        # Bloqueo 2: Máximo de trades diarios
        if self.trades_today >= self.max_daily_trades:
            return json.dumps({"decision": "HOLD", "reason": "Máximo de trades Kamikaze alcanzado."})

        # Bloqueo 3: No comprar en euforia extrema (protección macro)
        if fg_value > 75:
            return json.dumps({"decision": "HOLD", "reason": "MACRO_EXTREME_GREED_BLOCK"})

        if df is None or len(df) < 14:
            return json.dumps({"decision": "HOLD", "reason": "Data insuficiente"})

        # Indicadores técnicos
        df['RSI_14'] = ta.rsi(df['Close'], length=14)
        df.fillna(0, inplace=True)

        current_rsi = float(df.iloc[-1]['RSI_14'])
        current_price = float(df.iloc[-1]['Close'])
        score = float(social_data.get("score", 0.5))

        # MACD para confirmación
        macd_data = ta.macd(df['Close'])
        macd_bullish = False
        if macd_data is not None:
            try:
                macd_val = float(macd_data['MACD_12_26_9'].iloc[-1])
                macd_sig = float(macd_data['MACDs_12_26_9'].iloc[-1])
                macd_bullish = macd_val > macd_sig
            except Exception:
                pass

        # ============================================================
        # LÓGICA KAMIKAZE (Agresiva)
        # FIX-M1: Evaluar sobrecompra ANTES que momentum
        # FIX-MATH: score >= 0.5 en vez de > 0.5 (el default es 0.5)
        # ============================================================
        decision_matematica = "HOLD"
        reason_detail = ""

        # 1ro: Sobrecalentamiento → SELL (prioridad máxima)
        if current_rsi > 78:
            decision_matematica = "SELL"
            reason_detail = f"RSI={current_rsi:.1f} > 78: SOBRECALENTADO"

        # 2do: Momentum + hype → BUY (agresivo)
        elif current_rsi > 55 and score >= 0.5 and macd_bullish:
            decision_matematica = "BUY"
            reason_detail = f"RSI={current_rsi:.1f} + Hype={score:.2f} + MACD↑: MOMENTUM"

        # 3ro: Momentum fuerte sin MACD pero con hype alto
        elif current_rsi > 60 and score >= 0.6:
            decision_matematica = "BUY"
            reason_detail = f"RSI={current_rsi:.1f} + Hype={score:.2f}: HYPE_MOMENTUM"

        # 4to: Sobreventa extrema → BUY (oportunidad de rebote)
        elif current_rsi < 30:
            decision_matematica = "BUY"
            reason_detail = f"RSI={current_rsi:.1f} < 30: SOBREVENTA_EXTREMA"

        # 5to: Miedo extremo en F&G + RSI bajo → BUY contrarian
        elif fg_value < 25 and current_rsi < 40:
            decision_matematica = "BUY"
            reason_detail = f"F&G={fg_value} + RSI={current_rsi:.1f}: CONTRARIAN"

        else:
            reason_detail = f"RSI={current_rsi:.1f} Hype={score:.2f} MACD={'↑' if macd_bullish else '↓'}: Sin señal"

        # ============================================================
        # VELOCIDAD SOTA: Decisiones 100% locales (0ms)
        # ============================================================
        return json.dumps({
            "decision": decision_matematica,
            "reason": f"[KMZ|0ms] {reason_detail}"
        })