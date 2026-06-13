"""
EEA-2026-ANT: core/reddit_sensor.py
Sensor de Reddit — Sentimiento de r/cryptocurrency via RSS (gratis, sin API key).
Lee los títulos de los posts más recientes y analiza el sentimiento general.
"""
import logging
import requests
import re
import time

log = logging.getLogger("EEA-2026")

# Palabras que indican sentimiento positivo/negativo
BULLISH_WORDS = {
    'bull', 'bullish', 'moon', 'pump', 'surge', 'breakout', 'rally',
    'soar', 'gain', 'profit', 'buy', 'long', 'uptrend', 'ath',
    'adoption', 'partnership', 'upgrade', 'launch', 'all-time high',
    'record', 'recover', 'growth', 'positive', 'strong', 'rocket'
}

BEARISH_WORDS = {
    'bear', 'bearish', 'crash', 'dump', 'drop', 'fall', 'collapse',
    'scam', 'rug', 'hack', 'exploit', 'sell', 'short', 'downtrend',
    'fear', 'panic', 'warning', 'fraud', 'lawsuit', 'ban',
    'regulation', 'bubble', 'loss', 'negative', 'weak', 'danger'
}


class RedditSensor:
    """
    Lee RSS de r/cryptocurrency y r/CryptoMarkets para sentimiento.
    No necesita API key — usa el feed JSON público de Reddit.
    """

    def __init__(self):
        self.subreddits = [
            "cryptocurrency",
            "CryptoMarkets",
            "Bitcoin",
            "ethereum",
            "solana"
        ]
        self._cache = {}
        self._cache_ts = 0
        self.CACHE_TTL = 600  # 10 minutos

        self.headers = {
            'User-Agent': 'EEA2026-Bot/1.0 (Trading Research)'
        }

        log.info("[RedditSensor] 📡 Sensor Reddit activo (RSS gratuito)")

    def get_subreddit_sentiment(self, subreddit="cryptocurrency"):
        """
        Lee los últimos 25 posts de un subreddit y calcula sentimiento.
        Retorna: {"score": 0.0-1.0, "bullish": N, "bearish": N, "posts": N}
        """
        now = time.time()
        cache_key = subreddit

        if cache_key in self._cache and (now - self._cache_ts < self.CACHE_TTL):
            return self._cache[cache_key]

        try:
            url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit=25"
            resp = requests.get(url, headers=self.headers, timeout=10)

            if resp.status_code == 429:
                log.warning("[RedditSensor] Rate limited. Usando caché.")
                return self._cache.get(cache_key, {"score": 0.5, "posts": 0})

            if resp.status_code != 200:
                return {"score": 0.5, "posts": 0}

            data = resp.json()
            posts = data.get("data", {}).get("children", [])

            bullish_count = 0
            bearish_count = 0
            total_scored = 0

            for post in posts:
                post_data = post.get("data", {})
                title = post_data.get("title", "").lower()
                flair = (post_data.get("link_flair_text", "") or "").lower()
                ups = post_data.get("ups", 0)

                # Peso por upvotes (posts populares pesan más)
                weight = min(3, max(1, ups // 100))

                text = f"{title} {flair}"

                bull_hits = sum(1 for w in BULLISH_WORDS if w in text)
                bear_hits = sum(1 for w in BEARISH_WORDS if w in text)

                if bull_hits > bear_hits:
                    bullish_count += weight
                    total_scored += weight
                elif bear_hits > bull_hits:
                    bearish_count += weight
                    total_scored += weight

            if total_scored == 0:
                score = 0.5
            else:
                score = round(bullish_count / total_scored, 3)

            result = {
                "score": score,
                "bullish": bullish_count,
                "bearish": bearish_count,
                "posts": len(posts),
                "subreddit": subreddit
            }

            self._cache[cache_key] = result
            self._cache_ts = now

            emoji = "🟢" if score > 0.6 else ("🔴" if score < 0.4 else "⚪")
            log.info(
                f"[RedditSensor] {emoji} r/{subreddit}: "
                f"score {score:.2f} (🐂{bullish_count} 🐻{bearish_count})"
            )

            return result

        except Exception as e:
            log.warning(f"[RedditSensor] Error en r/{subreddit}: {e}")
            return {"score": 0.5, "posts": 0}

    def get_crypto_sentiment(self, ticker):
        """
        Calcula sentimiento combinado de múltiples subreddits
        relevantes para una cripto específica.
        """
        base = ticker.replace("-USD", "").lower()

        # Mapeo de ticker a subreddits relevantes
        ticker_subs = {
            "btc": ["Bitcoin", "cryptocurrency"],
            "eth": ["ethereum", "cryptocurrency"],
            "sol": ["solana", "cryptocurrency"],
            "xrp": ["XRP", "cryptocurrency"],
            "doge": ["dogecoin", "cryptocurrency"],
            "ada": ["cardano", "cryptocurrency"],
        }

        subs = ticker_subs.get(base, ["cryptocurrency"])

        scores = []
        for sub in subs:
            result = self.get_subreddit_sentiment(sub)
            scores.append(result.get("score", 0.5))

        if scores:
            avg_score = sum(scores) / len(scores)
            return round(avg_score, 3)
        return 0.5
