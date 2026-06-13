"""
EEA-2026-ANT: core/exchange_router.py
Router de ejecución de órdenes — Binance Testnet/Producción.
"""
import os
import sys
import subprocess
import logging
import asyncio

try:
    import ccxt
except ImportError:
    print("\n🚨 [SISTEMA] Librería 'ccxt' no detectada. Auto-instalando...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "ccxt"])
    import ccxt

log = logging.getLogger("EEA-2026")

class ExchangeRouter:
    def __init__(self, use_testnet=True):
        self.use_testnet = use_testnet
        if self.use_testnet:
            api_key = os.getenv("BINANCE_TESTNET_KEY")
            api_secret = os.getenv("BINANCE_TESTNET_SECRET")
            log.info("[ExchangeRouter] [WARN] MODO TESTNET ACTIVO")
        else:
            api_key = os.getenv("BINANCE_API_KEY")
            api_secret = os.getenv("BINANCE_API_SECRET")
        
        if not api_key or not api_secret:
            log.error("[ExchangeRouter] Faltan credenciales en .env")
            self.exchange = None
            return

        self.exchange = ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        if self.use_testnet:
            self.exchange.set_sandbox_mode(True)
        try:
            self.exchange.load_markets()
            log.info("[ExchangeRouter] ✅ Mercados y Reglas de Precisión cargadas.")
        except Exception as e:
            log.error(f"[ExchangeRouter] ❌ Error conectando a Binance: {e}")
            self.exchange = None

    def get_usdt_balance(self):
        if not self.exchange: return 0.0
        try:
            balance = self.exchange.fetch_balance()
            return balance.get('USDT', {}).get('free', 0.0)
        except Exception: return 0.0

    async def execute_market_order(self, symbol, side, amount_usd):
        if not self.exchange: return None
        try:
            binance_symbol = symbol.replace('-USD', '/USDT')
            orderbook = self.exchange.fetch_order_book(binance_symbol, limit=5)
            if side == 'buy': target_price = orderbook['asks'][0][0]
            else: target_price = orderbook['bids'][0][0]

            raw_amount = amount_usd / target_price
            f_amount = float(self.exchange.amount_to_precision(binance_symbol, raw_amount))
            f_price = float(self.exchange.price_to_precision(binance_symbol, target_price))
            if f_amount <= 0: return None

            order = self.exchange.create_limit_order(binance_symbol, side, f_amount, f_price)
            order_id = order['id']
            
            for _ in range(5):
                await asyncio.sleep(1.5)
                fetched = self.exchange.fetch_order(order_id, binance_symbol)
                if fetched.get('status') == 'closed':
                    return {
                        "id": order_id, "price": fetched.get('average', f_price),
                        "amount": fetched.get('filled', f_amount),
                        "cost": fetched.get('cost', f_price * f_amount)
                    }
                elif fetched.get('status') in ['canceled', 'expired']: return None
            
            try: 
                self.exchange.cancel_order(order_id, binance_symbol)
            except: 
                pass
            return None
        except Exception as e:
            log.error(f"[ExchangeRouter] ❌ Falla: {e}")
            return None

    async def execute_oco_order(self, symbol, side, amount, stop_loss_price, take_profit_price):
        """
        Ejecuta una orden OCO (One-Cancels-the-Other).
        En Testnet puede ser simulada si el exchange no la soporta.
        """
        if not self.exchange: return None
        try:
            binance_symbol = symbol.replace('-USD', '/USDT')
            
            log.info(f"[ExchangeRouter] [GUARD] Lanzando OCO en {symbol}: SL ${stop_loss_price:.2f} | TP ${take_profit_price:.2f}")
            
            try:
                # Intento de OCO nativo
                order = self.exchange.privatePostOrderOco({
                    'symbol': binance_symbol.replace('/', ''),
                    'side': side.upper(),
                    'quantity': self.exchange.amount_to_precision(binance_symbol, amount),
                    'price': self.exchange.price_to_precision(binance_symbol, take_profit_price),
                    'stopPrice': self.exchange.price_to_precision(binance_symbol, stop_loss_price),
                    'stopLimitPrice': self.exchange.price_to_precision(binance_symbol, stop_loss_price * 0.99),
                    'stopLimitTimeInForce': 'GTC'
                })
                return order
            except Exception as e:
                log.warning(f"[ExchangeRouter] [WARN] OCO nativo fallo ({e}). Usando simulador de seguridad.")
                # El simulador de seguridad ya está integrado en la Amígdala (WebSockets)
                return {"id": "SIMULATED_OCO", "status": "open"}

        except Exception as e:
            log.error(f"[ExchangeRouter] ❌ Error OCO: {e}")
            return None

    def cancel_all_orders(self, symbol):
        if not self.exchange: return
        try:
            binance_symbol = symbol.replace('-USD', '/USDT')
            self.exchange.cancel_all_orders(binance_symbol)
        except Exception as e:
            log.error(f"[ExchangeRouter] ❌ Falla al cancelar órdenes: {e}")