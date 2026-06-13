import ccxt
import logging

class ArbitrageAgent:
    def __init__(self):
        # Conexiones públicas para lectura de precios reales
        # Corregido: 'coinbaseexchange' es el nombre actual en ccxt para la API de intercambio
        self.binance = ccxt.binance()
        self.coinbase = ccxt.coinbaseexchange() 

    def find_opportunities(self, ticker, local_price):
        """Compara precios reales entre exchanges para detectar brechas de beneficio."""
        try:
            # Adaptar ticker de Yahoo Finance a formato Exchange (ej: BTC-USD -> BTC/USD)
            symbol = ticker.replace('-', '/')
            
            # Los activos que no son cripto se saltan en este agente
            if symbol == "NVDA/USD" or symbol == "AMD/USD":
                return {"spread_pct": 0, "opportunity": "STOCK_NOT_ON_CRYPTO_EXCHANGE"}

            # Obtener último precio de mercado de forma asíncrona (simulada aquí por ccxt)
            b_ticker = self.binance.fetch_ticker(symbol)
            c_ticker = self.coinbase.fetch_ticker(symbol)
            
            p_binance = b_ticker['last']
            p_coinbase = c_ticker['last']
            
            # Cálculo del Spread
            spread = abs(p_binance - p_coinbase)
            spread_pct = (spread / min(p_binance, p_coinbase)) * 100
            
            opportunity = "NONE"
            if p_binance < p_coinbase * 0.995: # Diferencia de 0.5%
                opportunity = "BUY_BINANCE_SELL_COINBASE"
            elif p_coinbase < p_binance * 0.995:
                opportunity = "BUY_COINBASE_SELL_BINANCE"
                
            return {
                "spread_pct": round(spread_pct, 2),
                "opportunity": opportunity,
                "prices": {"binance": p_binance, "coinbase": p_coinbase}
            }
        except Exception as e:
            return {"spread_pct": 0, "opportunity": "API_ERROR", "details": str(e)}