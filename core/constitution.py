"""
EEA-2026-ANT: core/constitution.py
La Constitución del Fondo — Reglas Inamovibles de Riesgo y Supervivencia.
"""
import logging

log = logging.getLogger("EEA-2026")

class AIConstitution:
    def __init__(self):
        # Reglas de Oro
        self.LAWS = [
            "1. Preservación del Capital: No arriesgar más del 30% del patrimonio total en una sola sesión.",
            "2. Anti-Fomo: No comprar activos con RSI > 85, sin importar el hype.",
            "3. Límite de Volatilidad: No operar si el spread Bid/Ask es > 1%.",
            "4. Seguridad OCO: Toda posición debe nacer con SL y TP en exchange.",
            "5. Calidad de Datos: No operar si el MarketSensor reporta latencia > 5s."
        ]

    def validate_proposal(self, ticker, indicators):
        """
        Valida una propuesta de compra contra las leyes de la constitución.
        Retorna: (is_legal, reason)
        """
        rsi = indicators.get("rsi", 50)
        spread = indicators.get("spread", 0)
        exposure = indicators.get("exposure", 0)

        # Validación Ley 2 (Anti-Fomo)
        if rsi > 85:
            return False, "VIOLACIÓN_LEY_2: RSI Extremo (Fomo Detectado)"

        # Validación Ley 3 (Spread)
        if spread > 0.01:
            return False, "VIOLACIÓN_LEY_3: Spread demasiado alto (Iliquidez)"

        # Validación Ley 1 (Exposición)
        if exposure > 0.35:
            return False, "VIOLACIÓN_LEY_1: Exposición excesiva de capital"

        return True, "CONSTITUCIONAL"

    def get_summary(self):
        return "\n".join(self.LAWS)
