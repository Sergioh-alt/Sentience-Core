"""
EEA-2026-ANT: core/prediction_agent.py
Oráculo de predicción — evalúa probabilidad de éxito basándose en noticias.
Migrado a ProviderPool centralizado.
"""
import json
import logging
from core.provider_pool import ProviderPool

log = logging.getLogger("EEA-2026")


class PredictionAgent:
    def __init__(self, aid="Predictor-Main"):
        self.aid = aid
        log.info(f"[{self.aid}] 🔮 Oráculo de predicción cargado (ProviderPool)")

    def evaluate_bet(self, ticker, price, news_summary):
        """Evalúa las probabilidades de éxito basándose en las noticias."""
        pool = ProviderPool.get()
        if pool.available_count == 0:
            return {"confidence": 0.5, "prediction": "HOLD"}

        prompt = (
            f"ACTIVO: {ticker} | PRECIO: ${price:.2f}\n"
            f"RESUMEN NOTICIAS: {news_summary}\n\n"
            f"Basado en esta información, estima la probabilidad matemática "
            f"de que el precio suba a corto plazo.\n"
            f"Responde SOLO con un JSON válido:\n"
            f'{{"confidence": 0.85, "prediction": "UP"}}\n'
            f"(Donde confidence es de 0.0 a 1.0)"
        )

        provider_name, content = pool.call_llm(prompt, temperature=0.2, timeout=10)

        if content:
            try:
                start = content.find('{')
                end = content.rfind('}')
                if start != -1 and end != -1:
                    result = json.loads(content[start:end + 1])
                    # Validar que confidence está en rango correcto
                    conf = float(result.get("confidence", 0.5))
                    conf = max(0.0, min(1.0, conf))
                    result["confidence"] = conf
                    return result
            except (json.JSONDecodeError, ValueError):
                pass

        return {"confidence": 0.5, "prediction": "HOLD"}