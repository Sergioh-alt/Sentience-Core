"""
EEA-2026-ANT: core/market_screener.py
El Ojo de Dios — Escanea TODO Binance buscando volatilidad.
MEJORADO:
- Blacklist de tokens peligrosos (rug pulls, dead coins, stablecoins)
- Filtro de precio mínimo ($0.0001 para evitar dust)
- Filtro de volumen real ($5M mínimo)
- Prioriza monedas con volumen/volatilidad combinada
"""
import ccxt
import logging

log = logging.getLogger("EEA-2026")

# =========================================================================
# BLACKLIST: Monedas que NUNCA se operan
# =========================================================================
BLACKLIST = {
    # Stablecoins (movimiento nulo = pérdida en comisiones)
    'USDC', 'USDT', 'BUSD', 'TUSD', 'FDUSD', 'DAI', 'FRAX', 'USDP',
    'PYUSD', 'GHO', 'CRVUSD', 'EURC', 'EURT',

    # Wrapped tokens (operar el original, no el wrapped)
    'WBTC', 'WETH', 'WBNB', 'WMATIC', 'STETH', 'RETH', 'CBETH',

    # Tokens con historial de manipulación o rug pull
    'LUNA', 'LUNC', 'UST', 'USTC', 'FTT',

    # Leveraged tokens (demasiado riesgo para un bot)
    'BTCUP', 'BTCDOWN', 'ETHUP', 'ETHDOWN', 'BNBUP', 'BNBDOWN',
    'XRPUP', 'XRPDOWN', 'ADAUP', 'ADADOWN',

    # EUR/GBP pairs (no son crypto)
    'EUR', 'GBP', 'TRY', 'BRL', 'ARS',
}


class MarketScreener:
    def __init__(self, use_testnet=True):
        self.exchange = ccxt.binance({
            'enableRateLimit': True,
            'options': {'defaultType': 'spot'}
        })
        if use_testnet:
            self.exchange.set_sandbox_mode(True)

        try:
            self.exchange.load_markets()
        except Exception as e:
            log.error(f"[Screener] Error cargando mercados: {e}")

    def get_top_volatile_assets(self, limit=3, min_volume_usd=5_000_000):
        """
        Escanea TODO Binance. Filtra por:
        1. Solo pares USDT
        2. No stablecoins, no wrapped, no leveraged, no blacklist
        3. Volumen > $5M (liquidez real)
        4. Precio > $0.0001 (evitar dust tokens)
        5. Ordena por SCORE = volatilidad × log(volumen)

        Retorna lista de tickers en formato yfinance (ej: "BTC-USD").
        """
        log.info("[Screener] Escaneando Binance...")
        try:
            tickers = self.exchange.fetch_tickers()
            valid_coins = []

            for symbol, data in tickers.items():
                # Regla 1: Solo pares USDT
                if not symbol.endswith('/USDT'):
                    continue

                # Regla 2: Blacklist
                base = symbol.split('/')[0]
                if base in BLACKLIST:
                    continue

                # Regla 3: Datos válidos
                vol_usd = data.get('quoteVolume', 0) or 0
                change_pct = abs(data.get('percentage', 0) or 0)
                last_price = data.get('last', 0) or 0

                # Regla 4: Liquidez y precio mínimo
                if vol_usd < min_volume_usd:
                    continue
                if last_price < 0.0001:
                    continue
                if change_pct <= 0:
                    continue

                # Score combinado: volatilidad * factor de volumen
                import math
                vol_factor = math.log10(max(vol_usd, 1)) / 10  # Normalizar 0-1
                score = change_pct * (1 + vol_factor)

                valid_coins.append({
                    'symbol': symbol.replace('/USDT', '-USD'),
                    'base': base,
                    'volume': vol_usd,
                    'volatility': change_pct,
                    'price': last_price,
                    'score': score
                })

            # Ordenar por score combinado (no solo volatilidad)
            valid_coins.sort(key=lambda x: x['score'], reverse=True)

            top = valid_coins[:limit]
            top_symbols = [coin['symbol'] for coin in top]

            if top_symbols:
                details = " | ".join([
                    f"{c['symbol']}({c['volatility']:.1f}%,${c['volume']/1e6:.0f}M)"
                    for c in top
                ])
                log.info(f"[Screener] Top {limit}: {details}")
                return top_symbols
            else:
                raise ValueError("Ninguna moneda pasó los filtros.")

        except Exception as e:
            log.error(f"[Screener] ❌ Fallo en radar: {e}. Modo supervivencia.")
            return ["BTC-USD", "ETH-USD", "DOGE-USD"]

    def get_meme_opportunities(self, min_volume_usd=2_000_000, min_change_pct=10.0):
        """
        Scanner especializado en meme coins / micro caps con movimiento extremo.
        Busca monedas con >10% de cambio y >$2M de volumen.
        Más agresivo que el scanner normal.
        """
        log.info("[Screener] 🎰 Buscando oportunidades meme/micro-cap...")
        try:
            tickers = self.exchange.fetch_tickers()
            meme_candidates = []

            for symbol, data in tickers.items():
                if not symbol.endswith('/USDT'):
                    continue
                base = symbol.split('/')[0]
                if base in BLACKLIST:
                    continue

                vol_usd = data.get('quoteVolume', 0) or 0
                change_pct = data.get('percentage', 0) or 0  # Con signo
                last_price = data.get('last', 0) or 0

                # Meme coins: cambio > 10%, volumen > $2M, precio > 0
                if (abs(change_pct) >= min_change_pct and
                        vol_usd >= min_volume_usd and
                        last_price > 0.0001):
                    meme_candidates.append({
                        'symbol': symbol.replace('/USDT', '-USD'),
                        'change_pct': change_pct,
                        'volume': vol_usd,
                        'price': last_price,
                        'direction': 'PUMP' if change_pct > 0 else 'DUMP'
                    })

            meme_candidates.sort(key=lambda x: abs(x['change_pct']), reverse=True)

            if meme_candidates:
                log.info(f"[Screener] 🎰 {len(meme_candidates)} memes detectados: "
                         f"{[c['symbol'] for c in meme_candidates[:5]]}")
            return meme_candidates[:5]

        except Exception as e:
            log.error(f"[Screener] Error buscando memes: {e}")
            return []

    def get_traditional_assets(self):
        """
        Retorna la lista de activos tradicionales (Acciones, Sectores y Oro).
        Usa formato yfinance.
        """
        return ["SPY", "QQQ", "XLK", "XLF", "XLE", "NVDA", "TSLA", "MSTR", "GC=F"]