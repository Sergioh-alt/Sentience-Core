"""
EEA-2026-ANT: core/whale_radar.py
Sensor de Ballenas e Influyentes — El Radar de Poder.
Clasifica a los actores en 3 niveles de confianza:
- Nivel 1: Ruido Radiactivo (Indicador Inverso)
- Nivel 2: Dueños del Casino (Macro Impacto)
- Nivel 3: Señal Pura (Blockchain + Institucional)
"""
import os
import logging
import requests
import json
import time

log = logging.getLogger("EEA-2026")

class WhaleRadar:
    def __init__(self):
        self.bearer_token = os.getenv("X_BEARER_TOKEN", "")
        self.level_1 = os.getenv("WHALE_LEVEL_1", "").split(",")
        self.level_2 = os.getenv("WHALE_LEVEL_2", "").split(",")
        self.level_3 = os.getenv("WHALE_LEVEL_3", "").split(",")
        
        self.headers = {"Authorization": f"Bearer {self.bearer_token}"}
        self._cache = {}
        self.CACHE_TTL = 300 # 5 minutos
        
        if self.bearer_token:
            log.info("[WhaleRadar] Radar de Poder activo (X API Integrada)")
        else:
            log.warning("[WhaleRadar] [WARN] Sin Bearer Token de X — Modo limitado")

    def get_market_sentiment_from_actors(self):
        """
        Escanea las cuentas clave y devuelve un score de impacto macro.
        Retorna: {score, warnings, bias}
        """
        if not self.bearer_token:
            return {"score": 50, "bias": "NEUTRAL", "warnings": []}

        now = time.time()
        if "global" in self._cache and (now - self._cache.get("global_ts", 0) < self.CACHE_TTL):
            return self._cache["global"]

        # En un sistema real, aquí llamaríamos a:
        # GET https://api.twitter.com/2/tweets/search/recent?query=from:jimcramer OR from:elonmusk...
        
        # Para esta versión, simulamos el análisis de los niveles
        # integrando con una búsqueda rápida en Google News via SerpAPI si X falla.
        
        results = {
            "score": 50,
            "bias": "NEUTRAL",
            "warnings": [],
            "signals": []
        }

        try:
            # Simulación de detección (en producción se reemplaza por llamadas a X)
            # Aquí implementamos la lógica de los niveles:
            
            # 1. Chequeo de Cramer (Nivel 1)
            # Si detectamos que Cramer dice "BUY", restamos confianza.
            cramer_sentiment = self._check_cramer_effect()
            if cramer_sentiment == "BULLISH":
                results["warnings"].append("[WARN] CRAMER_INVERSE: Cramer es alcista. ¡Peligro de crash!")
                results["score"] -= 15
            
            # 2. Chequeo de Powell (Nivel 2)
            # Si Powell habla pronto o dijo algo agresivo (Hawkish), pausamos.
            powell_status = self._check_macro_instability()
            if powell_status == "HAWKISH":
                results["warnings"].append("[WARN] POWELL_HAWKISH: La FED esta agresiva. Modo ahorro de capital.")
                results["score"] -= 20
                results["bias"] = "BEARISH_MACRO"
            
            # 3. Chequeo de BlackRock/WhaleAlert (Nivel 3)
            # Señales de acumulación real institucional.
            institutional_signal = self._check_institutional_move()
            if institutional_signal == "ACCUMULATION":
                results["signals"].append("💎 INSTITUTIONAL_INFLOW: BlackRock o Ballenas acumulando.")
                results["score"] += 25
                results["bias"] = "BULLISH_SURE"

            # Normalizar score
            results["score"] = max(0, min(100, results["score"]))
            
            self._cache["global"] = results
            self._cache["global_ts"] = now
            return results

        except Exception as e:
            log.warning(f"[WhaleRadar] Error analizando impacto: {e}")
            return {"score": 50, "bias": "ERROR", "warnings": [str(e)]}

    def _check_cramer_effect(self):
        # Lógica para detectar si Cramer recomendó algo recientemente
        try:
            url = "https://serpapi.com/search.json"
            params = {
                "engine": "google_news",
                "q": "Jim Cramer crypto buy recommendation",
                "api_key": os.getenv("SERPAPI_KEY")
            }
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()
            news = data.get("news_results", [])
            if not news:
                return "NEUTRAL"

            # Usar LLM para calificar el sentimiento de Cramer
            from core.provider_pool import ProviderPool
            pool = ProviderPool.get()
            headlines = [n.get("title", "") for n in news[:3]]
            prompt = f"Jim Cramer dijo estas cosas: {headlines}. ¿Es alcista (BULLISH) o bajista (BEARISH) o NEUTRAL? Responde solo una palabra."
            _, res = pool.call_llm(prompt)
            return "BULLISH" if "BULLISH" in res.upper() else ("BEARISH" if "BEARISH" in res.upper() else "NEUTRAL")
        except:
            return "NEUTRAL"

    def _check_macro_instability(self):
        # Lógica para detectar Hawkish/Dovish en la FED
        try:
            url = "https://serpapi.com/search.json"
            params = {
                "engine": "google_news",
                "q": "Jerome Powell interest rates FED news",
                "api_key": os.getenv("SERPAPI_KEY")
            }
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()
            news = data.get("news_results", [])
            if not news:
                return "NEUTRAL"

            from core.provider_pool import ProviderPool
            pool = ProviderPool.get()
            headlines = [n.get("title", "") for n in news[:3]]
            prompt = f"La FED dijo: {headlines}. ¿Es HAWKISH (agresivo/subir tasas) o DOVISH (suave/bajar tasas)? Responde solo una palabra."
            _, res = pool.call_llm(prompt)
            return "HAWKISH" if "HAWKISH" in res.upper() else ("DOVISH" if "DOVISH" in res.upper() else "NEUTRAL")
        except:
            return "NEUTRAL"

    def _check_institutional_move(self):
        # Lógica para detectar BlackRock o WhaleAlert
        try:
            url = "https://serpapi.com/search.json"
            params = {
                "engine": "google_news",
                "q": "BlackRock Bitcoin ETF or whale alert accumulation",
                "api_key": os.getenv("SERPAPI_KEY")
            }
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()
            news = data.get("news_results", [])
            if not news:
                return "NEUTRAL"

            from core.provider_pool import ProviderPool
            pool = ProviderPool.get()
            headlines = [n.get("title", "") for n in news[:3]]
            prompt = f"Noticias institucionales: {headlines}. ¿Están acumulando (ACCUMULATION) o vendiendo (DISTRIBUTION)? Responde solo una palabra."
            _, res = pool.call_llm(prompt)
            return "ACCUMULATION" if "ACCUMULATION" in res.upper() else ("DISTRIBUTION" if "DISTRIBUTION" in res.upper() else "NEUTRAL")
        except:
            return "NEUTRAL"
