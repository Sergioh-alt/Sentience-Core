"""
EEA-2026-ANT: core/orderbook_sensor.py
Analizador de Profundidad de Mercado (Order Book Imbalance).
Detecta muros de compra/venta para anticipar movimientos.
"""
import logging
import time

log = logging.getLogger("EEA-2026")

class OrderBookSensor:
    def __init__(self, exchange_router):
        self.router = exchange_router
        self._cache = {}
        self._wall_history = {} # {symbol: {price: vol, 'last_ts': ts}}

    def analyze_imbalance(self, symbol):
        """
        Calcula el ratio de desequilibrio y detecta Spoofing (Muros Falsos).
        """
        if not self.router or not self.router.exchange:
            return {"ratio": 1.0, "status": "NEUTRAL", "walls": [], "spoofing": False}

        try:
            binance_symbol = symbol.replace('-USD', '/USDT')
            ob = self.router.exchange.fetch_order_book(binance_symbol, limit=20)
            
            bids = ob['bids']
            asks = ob['asks']

            if not bids or not asks:
                return {"ratio": 1.0, "status": "NEUTRAL", "spoofing": False}

            total_bid_vol = sum([b[1] for b in bids])
            total_ask_vol = sum([a[1] for a in asks])
            imbalance_ratio = total_bid_vol / total_ask_vol if total_ask_vol > 0 else 1.0
            
            # --- DETECTOR DE SPOOFING (Fase Pro) ---
            spoofing_detected = False
            # Un muro es > 200% del promedio o un valor absoluto significativo
            avg_vol = total_bid_vol / len(bids) if bids else 0
            current_walls = {b[0]: b[1] for b in bids if b[1] > avg_vol * 1.5 or b[1] > 1.0} # 1.0 BTC es un muro real
            
            if symbol in self._wall_history:
                old_walls = self._wall_history[symbol]
                for price, old_vol in old_walls.items():
                    if price not in current_walls:
                        # Si desaparece un muro de > 0.3 BTC (~$20k) sin volumen de ejecución
                        if old_vol > 0.3: 
                            log.warning(f"[WARN] [SPOOFING] Muro en {price} desaparecio sospechosamente en {symbol}")
                            spoofing_detected = True
            
            self._wall_history[symbol] = current_walls
            
            status = "NEUTRAL"
            if imbalance_ratio > 1.5: status = "STRONG_BUY_PRESSURE"
            elif imbalance_ratio > 1.2: status = "BUY_PRESSURE"
            elif imbalance_ratio < 0.5: status = "STRONG_SELL_PRESSURE"
            elif imbalance_ratio < 0.8: status = "SELL_PRESSURE"

            walls = [{"type": "BUY_WALL", "price": p, "vol": v} for p, v in current_walls.items()]
            
            return {
                "ratio": round(imbalance_ratio, 2),
                "status": status,
                "total_bid_vol": round(total_bid_vol, 4),
                "total_ask_vol": round(total_ask_vol, 4),
                "walls": walls[:2],
                "spoofing": spoofing_detected
            }

        except Exception as e:
            log.debug(f"[OrderBookSensor] Error analizando {symbol}: {e}")
            return {"ratio": 1.0, "status": "ERROR", "spoofing": False}
