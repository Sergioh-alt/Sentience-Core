"""
EEA-2026-ANT: core/social_sensor.py
Pentágono de Datos — Recopila noticias de 6 fuentes y evalúa sentimiento.
Migrado a ProviderPool centralizado.
"""
import os
import json
import requests
import logging
import random

from core.provider_pool import ProviderPool
from core.nlp_sensor import NLPSensor

log = logging.getLogger("EEA-2026")


class SocialSensor:
    def __init__(self):
        self.tavily_keys = [
            os.getenv(f"TAVILY_API_KEY_{i}")
            for i in range(6) if os.getenv(f"TAVILY_API_KEY_{i}")
        ]
        self.news_api_key = os.getenv("NEWSAPI_KEY")
        self.exa_key = os.getenv("Exa_ai")
        self.finnhub_key = os.getenv("Finnhub_io")
        self.gnews_key = os.getenv("Gnews_io")
        self.lunar_key = os.getenv("LunarCrush_API_Key")

        log.info("[SocialSensor] 📡 Pentágono de Datos activado.")

    def _fetch_gnews(self, ticker):
        if not self.gnews_key:
            return ""
        try:
            url = (f"https://gnews.io/api/v4/search?q={ticker} crypto"
                   f"&lang=en&max=2&apikey={self.gnews_key}")
            res = requests.get(url, timeout=5).json()
            return "\n".join([f"- [Gnews] {a['title']}" for a in res.get("articles", [])])
        except Exception:
            return ""

    def _fetch_finnhub(self):
        if not self.finnhub_key:
            return ""
        try:
            url = f"https://finnhub.io/api/v1/news?category=crypto&token={self.finnhub_key}"
            res = requests.get(url, timeout=5).json()[:2]
            return "\n".join([f"- [Finnhub] {a['headline']}" for a in res])
        except Exception:
            return ""

    def _fetch_exa(self, ticker):
        if not self.exa_key:
            return ""
        try:
            headers = {"x-api-key": self.exa_key, "Content-Type": "application/json"}
            payload = {"query": f"In-depth analysis of {ticker} cryptocurrency today", "numResults": 2}
            res = requests.post("https://api.exa.ai/search", headers=headers,
                                json=payload, timeout=5).json()
            return "\n".join([f"- [Exa] {r['title']}" for r in res.get("results", [])])
        except Exception:
            return ""

    def _fetch_lunarcrush(self, ticker):
        """LunarCrush — placeholder hasta integración completa de API v4."""
        if not self.lunar_key:
            return ""
        # TODO: Integrar LunarCrush API v4 cuando esté disponible
        # Por ahora retorna vacío para no contaminar datos con info falsa
        return ""

    def _fetch_tavily(self, ticker):
        if not self.tavily_keys:
            return ""
        for key in random.sample(self.tavily_keys, min(2, len(self.tavily_keys))):
            try:
                payload = {
                    "api_key": key,
                    "query": f"latest {ticker} crypto news",
                    "search_depth": "basic",
                    "max_results": 2
                }
                res = requests.post("https://api.tavily.com/search",
                                    json=payload, timeout=5).json()
                return "\n".join([f"- [Tavily] {r['title']}" for r in res.get("results", [])])
            except Exception:
                pass
        return ""

    def _fetch_newsapi(self, ticker):
        if not self.news_api_key:
            return ""
        try:
            url = (f"https://newsapi.org/v2/everything?q={ticker} crypto"
                   f"&sortBy=publishedAt&pageSize=2&apiKey={self.news_api_key}")
            res = requests.get(url, timeout=5).json()
            return "\n".join([f"- [NewsAPI] {a['title']}" for a in res.get("articles", [])])
        except Exception:
            return ""

    def get_sentiment_score(self, ticker):
        """Recopila noticias en cascada y evalúa sentimiento con LLM."""
        news_data = []

        # Escuadrón Alfa: Gnews + Finnhub
        alfa_data = self._fetch_gnews(ticker) + "\n" + self._fetch_finnhub()
        if alfa_data.strip():
            news_data.append(alfa_data)

        # Escuadrón Beta: Exa + LunarCrush
        if len(news_data) < 2:
            beta_data = self._fetch_exa(ticker) + "\n" + self._fetch_lunarcrush(ticker)
            if beta_data.strip():
                news_data.append(beta_data)

        # Escuadrón Delta: Tavily + NewsAPI
        if not news_data:
            delta_data = self._fetch_tavily(ticker) + "\n" + self._fetch_newsapi(ticker)
            if delta_data.strip():
                news_data.append(delta_data)

        # Escuadrón Echo: Reddit RSS (gratis, sin API key)
        try:
            from core.reddit_sensor import RedditSensor
            reddit = RedditSensor()
            reddit_score = reddit.get_crypto_sentiment(ticker)
            news_data.append(f"- [Reddit] Sentimiento: {reddit_score:.2f}")
        except Exception:
            pass

        combined_news = "\n".join(news_data).strip()
        if not combined_news:
            return {"score": 0.5, "summary": "Sin datos de noticias disponibles."}

        # Evaluar sentimiento con FinBERT Local (GPU)
        nlp = NLPSensor.get()
        if getattr(nlp, 'pipeline', None):
            headlines = [line for line in combined_news.split('\n') if line.strip() and not line.startswith("- [Reddit]")]
            if not headlines:
                return {"score": 0.5, "summary": "Sin titulares procesables para FinBERT."}
                
            score = nlp.analyze_headlines(headlines)
            return {"score": score, "summary": f"Analizado localmente vía FinBERT ({len(headlines)} fuentes)."}
        else:
            # Fallback a ProviderPool si transformers no está instalado
            prompt = (
                f'Analiza estas noticias de {ticker}:\n{combined_news}\n'
                f'Evalúa el Hype de 0.0 a 1.0. '
                f'Responde SOLO JSON: {{"score": 0.8, "summary": "Resumen."}}'
            )

            pool = ProviderPool.get()
            provider_name, content = pool.call_llm(prompt, temperature=0.2, timeout=10)

            if content:
                try:
                    start = content.find('{')
                    end = content.rfind('}')
                    if start != -1 and end != -1:
                        result = json.loads(content[start:end + 1])
                        # Validar score en rango
                        result['score'] = max(0.0, min(1.0, float(result.get('score', 0.5))))
                        return result
                except (json.JSONDecodeError, ValueError):
                    pass

            return {"score": 0.5, "summary": "Pausa táctica de red."}