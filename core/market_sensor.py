"""
EEA-2026-ANT: core/market_sensor.py
Sensor de Mercado — Datos en tiempo real con multi-fuente y multi-timeframe.
MEJORAS:
- Fallback ccxt para monedas que yfinance no tiene
- Análisis multi-timeframe (15m + 1h confirmación)
- Detección de spikes de volumen
"""
import os
import logging
import pandas as pd
import pandas_ta as ta
import yfinance as yf
import requests

# Silenciar errores internos de yfinance para monedas no listadas
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

log = logging.getLogger("EEA-2026")

# Cache de tickers inválidos para evitar re-intentos innecesarios
INVALID_TICKERS_CACHE = set()


class MarketSensor:
    def __init__(self):
        self.tickers = ["BTC-USD", "ETH-USD", "DOGE-USD"]
        self.av_key = os.getenv("ALPHAVANTAGE_API_KEY")
        self._ccxt_exchange = None

    def _get_ccxt_exchange(self):
        """Lazy-load de ccxt para no consumir recursos si no se necesita."""
        if self._ccxt_exchange is None:
            try:
                import ccxt
                self._ccxt_exchange = ccxt.binance({
                    'enableRateLimit': True,
                    'options': {'defaultType': 'spot'}
                })
                self._ccxt_exchange.set_sandbox_mode(True)
                self._ccxt_exchange.load_markets()
            except Exception as e:
                log.warning(f"[MarketSensor] No se pudo iniciar ccxt fallback: {e}")
        return self._ccxt_exchange

    def _get_alphavantage_fallback(self, ticker):
        if not self.av_key:
            return 0
        try:
            if "-USD" in ticker:
                sym = ticker.replace("-USD", "")
                url = (f"https://www.alphavantage.co/query?function=CURRENCY_EXCHANGE_RATE"
                       f"&from_currency={sym}&to_currency=USD&apikey={self.av_key}")
                res = requests.get(url, timeout=5).json()
                return float(res.get("Realtime Currency Exchange Rate", {}).get("5. Exchange Rate", 0))
            else:
                url = (f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE"
                       f"&symbol={ticker}&apikey={self.av_key}")
                res = requests.get(url, timeout=5).json()
                return float(res.get("Global Quote", {}).get("05. price", 0))
        except Exception:
            return 0

    def get_live_data(self, extra_tickers=None):
        """Obtiene precios en vivo con cascada de fallbacks.
        Acepta tickers adicionales del screener."""
        all_tickers = list(set(self.tickers + (extra_tickers or [])))
        data = {}
        for t in all_tickers:
            if t in INVALID_TICKERS_CACHE:
                continue
            try:
                tkr = yf.Ticker(t)
                hist = tkr.history(period="1d", interval="15m")
                if hist.empty:
                    # Fallback 1: AlphaVantage
                    fallback_price = self._get_alphavantage_fallback(t)
                    if fallback_price > 0:
                        data[t] = {"status": "DATA_OK", "price": fallback_price}
                        log.info(f"[MarketSensor] [FALLBACK] AlphaVantage fallback: {t}")
                    else:
                        # Fallback 2: ccxt
                        ccxt_price = self._get_ccxt_price(t)
                        if ccxt_price > 0:
                            data[t] = {"status": "DATA_OK", "price": ccxt_price}
                            log.info(f"[MarketSensor] [FALLBACK] ccxt fallback: {t}")
                        else:
                            data[t] = {"status": "ERROR", "price": 0}
                    continue

                last_price = float(hist['Close'].iloc[-1])

                # Detección de mercado cerrado para acciones
                if t in ["AMD", "NVDA"] and len(hist) >= 3:
                    if (hist['Close'].iloc[-1] == hist['Close'].iloc[-2] ==
                            hist['Close'].iloc[-3]):
                        data[t] = {"status": "MARKET_CLOSED", "price": last_price}
                        continue

                data[t] = {"status": "DATA_OK", "price": last_price}
            except Exception as e:
                fallback_price = self._get_alphavantage_fallback(t)
                if fallback_price > 0:
                    data[t] = {"status": "DATA_OK", "price": fallback_price}
                else:
                    data[t] = {"status": "ERROR", "price": 0}
        return data

    def _get_ccxt_price(self, ticker):
        """Obtiene precio desde ccxt como último fallback."""
        exchange = self._get_ccxt_exchange()
        if not exchange:
            return 0
        try:
            binance_sym = ticker.replace('-USD', '/USDT')
            if binance_sym in exchange.markets:
                tkr = exchange.fetch_ticker(binance_sym)
                return float(tkr.get('last', 0))
        except Exception:
            pass
        return 0

    def get_technical_analysis(self, ticker, period="1d", interval="1m"):
        """
        Descarga datos históricos de Yahoo Finance y calcula indicadores.
        """
        if ticker in INVALID_TICKERS_CACHE:
            return None

        try:
            # Si el ticker tiene caracteres extraños, es basura
            if any(c in ticker for c in ["$", "!", "?", " "]) or len(ticker) > 15:
                INVALID_TICKERS_CACHE.add(ticker)
                return None

            data = yf.download(ticker, period=period, interval=interval, progress=False, show_errors=False)
            if data.empty:
                # Marcar como inválido si falla repetidamente
                log.debug(f"[MarketSensor] Ticker no encontrado en YF: {ticker}")
                return None
            
            df = data
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            if df is not None and not df.empty:
                return df
        except Exception:
            pass

        # Fallback: datos de ccxt
        return self.get_technical_analysis_ccxt(ticker)

    def get_technical_analysis_ccxt(self, ticker, exchange=None):
        """
        Fallback: obtiene OHLCV de ccxt para monedas que yfinance no tiene.
        """
        if exchange is None:
            exchange = self._get_ccxt_exchange()
        if not exchange or not hasattr(exchange, 'markets') or not exchange.markets:
            return None

        try:
            # Solo procesar si parece una cripto con par USD
            if "-USD" not in ticker:
                return None
                
            binance_sym = ticker.replace('-USD', '/USDT')
            if binance_sym not in exchange.markets:
                return None

            ohlcv = exchange.fetch_ohlcv(binance_sym, '15m', limit=100)
            if not ohlcv:
                return None

            df = pd.DataFrame(ohlcv, columns=['timestamp', 'Open', 'High', 'Low', 'Close', 'Volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            return df
        except Exception as e:
            # Silenciamos errores comunes de activos no encontrados
            return None

    def get_multi_timeframe_confirmation(self, ticker):
        """
        Análisis multi-timeframe: compara señales de 15m vs 1h.
        Si ambos timeframes coinciden, la señal es más fuerte.
        Retorna: "BULLISH", "BEARISH", o "NEUTRAL"
        """
        try:
            tkr = yf.Ticker(ticker)

            # Timeframe corto: 15 minutos
            df_15m = tkr.history(period="2d", interval="15m")
            if df_15m.empty or len(df_15m) < 20:
                return "NEUTRAL"

            # Timeframe largo: 1 hora
            df_1h = tkr.history(period="5d", interval="1h")
            if df_1h.empty or len(df_1h) < 20:
                return "NEUTRAL"

            # RSI en ambos timeframes
            rsi_15m = ta.rsi(df_15m['Close'], length=14)
            rsi_1h = ta.rsi(df_1h['Close'], length=14)

            if rsi_15m is None or rsi_1h is None:
                return "NEUTRAL"

            rsi_15m_val = float(rsi_15m.iloc[-1]) if len(rsi_15m) > 0 else 50
            rsi_1h_val = float(rsi_1h.iloc[-1]) if len(rsi_1h) > 0 else 50

            # MACD en 1h
            macd_1h = ta.macd(df_1h['Close'])
            macd_val = float(macd_1h['MACD_12_26_9'].iloc[-1]) if macd_1h is not None else 0
            macd_sig = float(macd_1h['MACDs_12_26_9'].iloc[-1]) if macd_1h is not None else 0

            # Señal combinada
            bullish_signals = 0
            bearish_signals = 0

            if rsi_15m_val < 45 and rsi_1h_val < 50:
                bullish_signals += 1
            if rsi_15m_val > 65 and rsi_1h_val > 60:
                bearish_signals += 1
            if macd_val > macd_sig:
                bullish_signals += 1
            else:
                bearish_signals += 1

            if bullish_signals > bearish_signals:
                return "BULLISH"
            elif bearish_signals > bullish_signals:
                return "BEARISH"
            return "NEUTRAL"

        except Exception:
            return "NEUTRAL"

    def detect_volume_spike(self, ticker, threshold=2.0):
        """
        Detecta spikes de volumen — señal de que algo importante está pasando.
        threshold: multiplicador sobre el volumen promedio.
        Retorna: True si hay spike, False si no.
        """
        try:
            tkr = yf.Ticker(ticker)
            df = tkr.history(period="5d", interval="1h")
            if df.empty or len(df) < 24:
                return False

            avg_volume = df['Volume'].iloc[-25:-1].mean()
            current_volume = df['Volume'].iloc[-1]

            if avg_volume > 0 and current_volume > avg_volume * threshold:
                log.info(f"[MarketSensor] 🔊 SPIKE DE VOLUMEN en {ticker}: "
                         f"{current_volume:,.0f} vs avg {avg_volume:,.0f}")
                return True
            return False
        except Exception:
            return False