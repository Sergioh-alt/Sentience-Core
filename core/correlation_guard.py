"""
EEA-2026-ANT: core/correlation_guard.py
Guardia de Correlación — Evita sobreexposición a activos correlacionados.
Si ya tienes BTC y ETH se mueve igual → no comprar ETH.
"""
import logging
import yfinance as yf
import pandas as pd

log = logging.getLogger("EEA-2026")


class CorrelationGuard:
    """
    Calcula correlación de precios entre activos para evitar
    tener posiciones en activos que se mueven igual.
    """

    def __init__(self, threshold=0.80):
        self.threshold = threshold  # Correlación > 0.80 = demasiado similar
        self._cache = {}
        self._cache_ts = 0
        self.CACHE_TTL = 3600  # Recalcular correlaciones cada hora

    def is_correlated_with_portfolio(self, new_ticker, portfolio_tickers):
        """
        Verifica si new_ticker está altamente correlacionado con
        algún activo que ya tenemos en portfolio.
        
        Returns:
            (bool, str): (is_correlated, reason)
        """
        if not portfolio_tickers:
            return False, ""

        import time
        now = time.time()

        for held_ticker in portfolio_tickers:
            if held_ticker == new_ticker:
                return True, f"Ya tenemos {new_ticker}"

            cache_key = f"{min(new_ticker, held_ticker)}_{max(new_ticker, held_ticker)}"

            # Usar caché si es reciente
            if cache_key in self._cache and (now - self._cache_ts < self.CACHE_TTL):
                corr = self._cache[cache_key]
            else:
                corr = self._calculate_correlation(new_ticker, held_ticker)
                self._cache[cache_key] = corr
                self._cache_ts = now

            if corr is not None and corr > self.threshold:
                log.warning(
                    f"[CorrelationGuard] [WARN] {new_ticker} correlacion {corr:.2f} "
                    f"con {held_ticker} (límite: {self.threshold})"
                )
                return True, f"Correlación {corr:.2f} con {held_ticker}"

        return False, ""

    def _calculate_correlation(self, ticker_a, ticker_b):
        """
        Calcula correlación de Pearson entre dos activos
        usando datos de 5 días en intervalos de 1h.
        """
        try:
            df_a = yf.Ticker(ticker_a).history(period="5d", interval="1h")
            df_b = yf.Ticker(ticker_b).history(period="5d", interval="1h")

            if df_a.empty or df_b.empty or len(df_a) < 20 or len(df_b) < 20:
                return None

            # Alinear por timestamp
            combined = pd.DataFrame({
                'a': df_a['Close'].pct_change().dropna(),
                'b': df_b['Close'].pct_change().dropna()
            }).dropna()

            if len(combined) < 20:
                return None

            corr = combined['a'].corr(combined['b'])
            return round(corr, 3) if pd.notna(corr) else None

        except Exception as e:
            log.warning(f"[CorrelationGuard] Error calculando correlación: {e}")
            return None

    def get_correlation_matrix(self, tickers):
        """Genera una matriz de correlación para una lista de activos."""
        results = {}
        for i, t1 in enumerate(tickers):
            for t2 in tickers[i + 1:]:
                corr = self._calculate_correlation(t1, t2)
                if corr is not None:
                    results[f"{t1}_vs_{t2}"] = corr
        return results
