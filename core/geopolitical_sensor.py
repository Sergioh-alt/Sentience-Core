import os
import requests
import logging
from core.provider_pool import ProviderPool

log = logging.getLogger("EEA-2026")

class GeopoliticalSensor:
    def __init__(self):
        self.serp_key = os.getenv("SERPAPI_KEY")
        self.aid = "Geo-Watcher"
        log.info(f"[{self.aid}] [GEO] Analista Geopolitico activado.")

    def get_geopolitical_risk(self):
        """
        Escanea el panorama mundial en busca de 'Cisnes Negros' o inestabilidad.
        Retorna un score de 0.0 (Paz total) a 1.0 (Caos/Riesgo extremo).
        """
        if not self.serp_key:
            return 0.2 # Riesgo base

        try:
            # Buscamos noticias de alto impacto geopolítico
            url = "https://serpapi.com/search.json"
            queries = [
                "world war tension news",
                "FED interest rate decision today",
                "global economic crisis news"
            ]
            
            combined_headlines = []
            for q in queries:
                params = {
                    "engine": "google_news",
                    "q": q,
                    "api_key": self.serp_key
                }
                res = requests.get(url, params=params, timeout=5).json()
                combined_headlines.extend([n.get("title", "") for n in res.get("news_results", [])[:2]])

            if not combined_headlines:
                return 0.3

            # Usamos IA para evaluar el nivel de peligro mundial
            prompt = (
                f"Analiza estos titulares mundiales con CRITERIO ESTOICO:\n{combined_headlines}\n"
                "Evalúa el riesgo REAL para los mercados financieros de 0.0 a 1.0.\n"
                "- 0.0 a 0.3: Ruido normal de noticias o tensiones diplomáticas menores.\n"
                "- 0.4 a 0.6: Eventos que pueden causar volatilidad (datos FED, elecciones).\n"
                "- 0.7 a 1.0: Crisis sistémicas, guerras activas o colapsos económicos.\n"
                "Sé escéptico. Si los titulares son ambiguos, mantente debajo de 0.5.\n"
                "Responde SOLO el número."
            )
            
            pool = ProviderPool.get()
            _, content = pool.call_llm(prompt, temperature=0.1)
            
            try:
                risk_score = float(content.strip())
                log.info(f"[{self.aid}] [GEO] Riesgo Geopolitico Detectado: {risk_score:.2f}")
                return max(0.0, min(1.0, risk_score))
            except:
                return 0.4
                
        except Exception as e:
            log.warning(f"[{self.aid}] Error en análisis geo: {e}")
            return 0.3
