"""
EEA-2026-ANT: core/trends_sensor.py
Sensor de Google Trends — Detecta qué criptomonedas están siendo
buscadas masivamente. Un spike en búsquedas de "Bitcoin" o "DOGE"
puede predecir movimiento de precio.
Usa SerpAPI (gratis, 100 búsquedas/mes).
"""
import os
import logging
import requests
import time

log = logging.getLogger("EEA-2026")


class TrendsSensor:
    def __init__(self):
        self.api_key = os.getenv("SERPAPI_KEY", "")
        self._cache = {}
        self._cache_ts = 0
        self.CACHE_TTL = 1800  # 30 minutos (conservar requests)

        if self.api_key:
            log.info("[TrendsSensor] Google Trends activo via SerpAPI")
        else:
            log.warning("[TrendsSensor] [WARN] Sin clave SERPAPI — Trends desactivado")

    def get_trending_interest(self, keyword):
        """
        Consulta el interés de búsqueda de una keyword en Google Trends.
        Retorna un score de 0-100 (100 = máximo interés).
        Usa caché de 30 min para no gastar requests.
        """
        if not self.api_key:
            return {"interest": 50, "source": "default"}

        now = time.time()
        if keyword in self._cache and (now - self._cache_ts < self.CACHE_TTL):
            return self._cache[keyword]

        try:
            url = "https://serpapi.com/search.json"
            params = {
                "engine": "google_trends",
                "q": keyword,
                "data_type": "TIMESERIES",
                "date": "now 7-d",
                "api_key": self.api_key
            }
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()

            # Extraer el interés más reciente
            timeline = data.get("interest_over_time", {}).get("timeline_data", [])
            if timeline:
                # Último punto de datos
                last = timeline[-1]
                values = last.get("values", [])
                if values:
                    interest = int(values[0].get("extracted_value", 50))
                    result = {"interest": interest, "source": "google_trends"}
                    self._cache[keyword] = result
                    self._cache_ts = now
                    log.info(f"[TrendsSensor] {keyword}: interes {interest}/100")
                    return result

            return {"interest": 50, "source": "no_data"}

        except Exception as e:
            log.warning(f"[TrendsSensor] Error: {e}")
            return {"interest": 50, "source": "error"}

    def get_crypto_hype_score(self, ticker):
        """
        Calcula un score de hype para una cripto basado en
        múltiples búsquedas relacionadas.
        """
        base_name = ticker.replace("-USD", "").lower()

        # Mapeo de tickers a nombres de búsqueda
        name_map = {
            "btc": "Bitcoin",
            "eth": "Ethereum",
            "sol": "Solana",
            "xrp": "XRP",
            "doge": "Dogecoin",
            "pepe": "PEPE coin",
            "shib": "Shiba Inu",
            "ada": "Cardano",
            "avax": "Avalanche crypto",
            "matic": "Polygon crypto",
            "link": "Chainlink",
            "dot": "Polkadot"
        }

        search_term = name_map.get(base_name, f"{base_name} crypto")
        result = self.get_trending_interest(search_term)
        return result.get("interest", 50)

    def is_trending_up(self, ticker, threshold=70):
        """
        Retorna True si la cripto tiene interés de búsqueda > threshold.
        Útil como señal adicional para el sistema de votos.
        """
        score = self.get_crypto_hype_score(ticker)
        return score >= threshold
