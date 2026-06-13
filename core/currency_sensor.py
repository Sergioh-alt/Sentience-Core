import yfinance as yf
import logging
import time

log = logging.getLogger("EEA-2026")

class CurrencySensor:
    def __init__(self):
        # Monitoreamos las divisas que mueven el mundo y tu meta local
        self.tickers = {
            "USDCOP": "COP=X",
            "EURUSD": "EURUSD=X",
            "DXY": "DX-Y.NYB" # Indice del Dolar
        }
        self._cache = {}
        self._last_update = 0
        self.TTL = 900 # 15 minutos

    def get_global_rates(self):
        """Obtiene las tasas de cambio y el pulso del dolar."""
        now = time.time()
        if now - self._last_update < self.TTL and self._cache:
            return self._cache

        results = {}
        for name, ticker in self.tickers.items():
            try:
                import time as t_sleep
                t_sleep.sleep(0.5) # Pequeño delay entre peticiones para yfinance
                data = yf.Ticker(ticker).history(period="1d")
                if not data.empty:
                    results[name] = round(data['Close'].iloc[-1], 2)
                else:
                    results[name] = 0.0
            except Exception as e:
                log.error(f"Error en divisa {name}: {e}")
                results[name] = 0.0
        
        if any(v > 0 for v in results.values()):
            self._cache = results
            self._last_update = now
        return results if results else self._cache