"""
EEA-2026-ANT: core/trader_agent.py
Brazo ejecutor del sistema — Compra/Vende en Binance.
VERSIÓN MEJORADA:
- FIX-M4: Patrimonio con precios de mercado
- NUEVO: Reasignación de Capital (F3 constitución)
- NUEVO: Trailing Stop dinámico basado en ATR
- NUEVO: Integración con Q-Table (aprendizaje adaptativo)
- NUEVO: Alertas Telegram
"""
import os
import logging
from datetime import datetime
from core.database_manager import DatabaseManager
from core.alerts import send_alert

try:
    from core.exchange_router import ExchangeRouter
except ImportError:
    pass

try:
    from core.q_table import QTable
except ImportError:
    QTable = None

log = logging.getLogger("EEA-2026")


class TraderAgent:
    def __init__(self, aid="Trader-Live-Testnet"):
        self.aid = aid

        self.MIN_TRADE_USD = 11.00
        self.MAX_AUTO_USD = 25.00
        self.KAMIKAZE_LIMIT = 15.00

        # Trailing stop base (se ajusta dinámicamente con ATR)
        self.TRAILING_STOP_PCT = 0.05
        self.TAKE_PROFIT_PCT = 0.15
        self.MAX_EXPOSURE = 0.30

        self.MAX_DAILY_TRADES = 3
        self.trades_today = 0
        self.last_trade_date = datetime.now().date()

        self.sim_cash = 0.0
        self.sim_portfolio = {}

        self.db = DatabaseManager()
        self.router = ExchangeRouter(use_testnet=True)
        self.db_positions = self.db.get_all_positions()

        # Dependencias externas (se inyectan desde el orquestador)
        self.kamikaze = None
        self.post_mortem = None
        self.weights = None

        # Q-Table para aprendizaje adaptativo
        self.q_table = QTable() if QTable else None

        # Guardar estado al momento de la compra (para post-mortem)
        self._trade_states = {}

        self.sync_balances()
        self.run_desync_audit()

    def set_dependencies(self, kamikaze=None, post_mortem=None, weights=None):
        """Inyecta dependencias circulares o externas."""
        self.kamikaze = kamikaze
        self.post_mortem = post_mortem
        self.weights = weights

    def run_desync_audit(self):
        log.info(f"[{self.aid}] 🔍 Auditoría de Desincronización...")
        db_pos = self.db.get_all_positions()
        for ticker in list(db_pos.keys()):
            qty = self.sim_portfolio.get(ticker, 0.0)
            if qty < 0.000001:
                log.warning(f"[{self.aid}] 🧹 Fantasma en {ticker}. Purgando.")
                self.db.delete_position(ticker)
        self.db_positions = self.db.get_all_positions()
        log.info(f"[{self.aid}] ✅ Auditoría completada.")

    def sync_balances(self):
        if self.router and self.router.exchange:
            try:
                balance = self.router.exchange.fetch_balance()
                # Ajuste: El balance libre es después de considerar órdenes abiertas (Fees)
                self.sim_cash = balance.get('USDT', {}).get('free', 0.0)
                
                # Inyección de capital simulado para Testnet si está en 0
                if self.sim_cash < 1.0:
                    self.sim_cash = 100.00
                    
                for coin_data in balance.get('info', {}).get('balances', []):
                    coin = coin_data['asset']
                    free_qty = float(coin_data['free'])
                    if coin != "USDT" and free_qty > 0:
                        self.sim_portfolio[f"{coin}-USD"] = free_qty
            except Exception as e:
                log.error(f"[{self.aid}] Error sincronizando: {e}")

    def get_dynamic_trailing(self, ticker, atr_value, current_price):
        """
        Trailing Stop dinámico basado en ATR.
        - Mínimo 3% (protección base)
        - Máximo 12% (para activos ultra-volátiles)
        - Fórmula: ATR_14 / precio_actual * 2.0
        """
        if atr_value and current_price > 0:
            dynamic = (atr_value / current_price) * 2.0
            return max(0.03, min(0.12, dynamic))
        return self.TRAILING_STOP_PCT  # Fallback al 5% fijo

    def get_slippage_estimate(self, ticker, amount_usd):
        """
        Calcula el impacto estimado en el precio (Slippage) antes de comprar.
        Retorna (avg_price, slippage_pct).
        """
        try:
            binance_symbol = ticker.replace('-USD', '/USDT')
            ob = self.router.exchange.fetch_order_book(binance_symbol, limit=20)
            asks = ob['asks']
            
            total_filled_usd = 0
            total_qty = 0
            initial_price = asks[0][0]
            
            for price, qty in asks:
                needed_usd = amount_usd - total_filled_usd
                level_usd = price * qty
                
                if level_usd >= needed_usd:
                    fill_qty = needed_usd / price
                    total_qty += fill_qty
                    total_filled_usd += needed_usd
                    break
                else:
                    total_qty += qty
                    total_filled_usd += level_usd
            
            if total_qty == 0: return initial_price, 0
            
            avg_price = total_filled_usd / total_qty
            slippage_pct = (avg_price - initial_price) / initial_price
            return avg_price, slippage_pct
        except:
            return 0, 0

    # =========================================================================
    # REFLEJO DE LA AMIGDALA (WEBSOCKETS)
    # =========================================================================
    def evaluate_risk_fast(self, ticker, current_price):
        """Ejecución de supervivencia. Solo SQL y Matemáticas."""
        try:
            qty = self.sim_portfolio.get(ticker, 0.0)
            if qty <= 0:
                return False

            pos_data = self.db_positions.get(ticker, {})
            entry = pos_data.get('entry', 0.0)
            highest = pos_data.get('highest', 0.0)

            if entry <= 0:
                return False

            if current_price > highest:
                self.db.update_highest_price(ticker, current_price)
                highest = current_price

            drawdown_pct = (current_price - highest) / highest
            profit_pct = (current_price - entry) / entry

            # Trailing stop (usa el valor guardado o el default)
            trailing = self.TRAILING_STOP_PCT

            decision = "HOLD"
            trigger_reason = ""

            if drawdown_pct <= -trailing:
                decision = "SELL"
                trigger_reason = "TRAILING_STOP_WS"
            elif profit_pct >= self.TAKE_PROFIT_PCT:
                decision = "SELL"
                trigger_reason = "TAKE_PROFIT_WS"

            if decision == "SELL":
                log.warning(f"[{self.aid}] [REFLEJO] {trigger_reason} en {ticker}!")
                valor_posicion_usd = qty * current_price
                order = self.router.execute_market_order(ticker, 'sell', valor_posicion_usd)

                if order:
                    precio_ejecucion = order['price']
                    
                    # Cálculo de Comisiones (0.1% Binance Standard)
                    fee_pct = 0.001 
                    valor_entrada = entry * qty
                    valor_salida = precio_ejecucion * qty
                    costo_fees = (valor_entrada * fee_pct) + (valor_salida * fee_pct)
                    
                    pnl_usd = (valor_salida - valor_entrada) - costo_fees
                    pnl_pct = (pnl_usd / valor_entrada * 100) if valor_entrada > 0 else 0

                    self.db.delete_position(ticker)
                    self.db.record_trade_pnl({
                        "timestamp": datetime.now().isoformat(),
                        "ticker": ticker,
                        "qty": order['amount'],
                        "entry_price": entry,
                        "exit_price": precio_ejecucion,
                        "pnl_usd": round(pnl_usd, 2),
                        "pnl_pct": round(pnl_pct, 2),
                        "trigger": trigger_reason
                    })

                    # Aprendizaje: registrar resultado en Q-Table
                    if ticker in self._trade_states:
                        market_conditions = self._trade_states.pop(ticker)
                        
                        # Registrar en Q-Table
                        if self.q_table:
                            state = market_conditions.get('market_state')
                            if state:
                                self.q_table.record_outcome(state, "BUY", pnl_usd > 0)
                        
                        # Análisis Post-Mortem (LLM)
                        if self.post_mortem:
                            trade_data = {
                                "ticker": ticker,
                                "entry_price": entry,
                                "exit_price": precio_ejecucion,
                                "pnl_usd": pnl_usd,
                                "pnl_pct": pnl_pct,
                                "trigger": trigger_reason,
                                "qty": order['amount']
                            }
                            self.post_mortem.analyze_closed_trade(trade_data, market_conditions)
                        
                        # Actualizar pesos de agentes (Reinforcement Loop v1.5)
                        if self.weights:
                            votes_cast = market_conditions.get("votes_cast", [])
                            self.weights.update_weights_from_pnl(votes_cast, pnl_usd > 0)

                    log.info(f"[{self.aid}] {emoji} VENTA | PnL: ${pnl_usd:.2f}")
                    
                    log.info(f"[{self.aid}] {emoji} VENTA | PnL: ${pnl_usd:.2f}")

                    send_alert(
                        f"{trigger_reason}\n{ticker}\n"
                        f"${entry:.2f} → ${precio_ejecucion:.2f}\n"
                        f"PnL: ${pnl_usd:.2f} ({pnl_pct:.1f}%)",
                        "STOP"
                    )
                    self.sync_balances()
                    return True
            return False
        except Exception as e:
            log.error(f"[{self.aid}] Error reflejo: {e}")
            return False

    # =========================================================================
    # 🔄 REASIGNACIÓN DE CAPITAL (F3 Constitución)
    # =========================================================================
    async def _try_reallocate_capital(self, new_ticker, new_price, votes, market_prices):
        """
        F3: Si hay una oportunidad de alta convicción pero no hay cash,
        vender la posición con peor rendimiento para financiar la nueva compra.
        
        Solo se ejecuta cuando:
        - votes >= 3 (máxima convicción)
        - cash < MIN_TRADE_USD
        - Hay al menos 1 posición existente con peor rendimiento
        """
        if votes < 3 or self.sim_cash >= self.MIN_TRADE_USD:
            return False  # No necesita reasignación

        if not market_prices or not self.sim_portfolio:
            return False

        log.info(f"[{self.aid}] 🔄 Evaluando Reasignación de Capital (F3)...")

        # Encontrar la posición con peor rendimiento
        worst_ticker = None
        worst_pnl_pct = float('inf')

        for held_ticker, qty in self.sim_portfolio.items():
            if qty <= 0 or held_ticker == new_ticker:
                continue

            entry_price = self.db_positions.get(held_ticker, {}).get('entry', 0)
            current_price = market_prices.get(held_ticker, {}).get('price', 0)

            if entry_price > 0 and current_price > 0:
                pnl_pct = (current_price - entry_price) / entry_price
                if pnl_pct < worst_pnl_pct:
                    worst_pnl_pct = pnl_pct
                    worst_ticker = held_ticker

        if worst_ticker is None:
            return False

        # Solo reasignar si la posición débil está peor que neutral
        if worst_pnl_pct > -0.02:  # Si solo está -2% o mejor, no vender
            log.info(f"[{self.aid}] 🔄 No hay posición lo suficientemente débil para reasignar")
            return False

        worst_qty = self.sim_portfolio.get(worst_ticker, 0)
        worst_price = market_prices.get(worst_ticker, {}).get('price', 0)
        worst_value = worst_qty * worst_price

        if worst_value < self.MIN_TRADE_USD:
            return False

        log.warning(
            f"[{self.aid}] 🔄 REASIGNACIÓN: Vendiendo {worst_ticker} "
            f"({worst_pnl_pct*100:.1f}%) para comprar {new_ticker}"
        )

        # Vender la posición débil
        sell_order = await self.router.execute_market_order(worst_ticker, 'sell', worst_value)
        if sell_order:
            entry_price = self.db_positions.get(worst_ticker, {}).get('entry', 0)
            
            # Cálculo de Comisiones (0.1%)
            fee_pct = 0.001 
            valor_entrada = entry_price * sell_order['amount']
            valor_salida = sell_order['price'] * sell_order['amount']
            costo_fees = (valor_entrada * fee_pct) + (valor_salida * fee_pct)
            
            pnl_usd = (valor_salida - valor_entrada) - costo_fees

            self.db.delete_position(worst_ticker)
            self.db.record_trade_pnl({
                "timestamp": datetime.now().isoformat(),
                "ticker": worst_ticker,
                "qty": sell_order['amount'],
                "entry_price": entry_price,
                "exit_price": sell_order['price'],
                "pnl_usd": round(pnl_usd, 2),
                "pnl_pct": round(worst_pnl_pct * 100, 2),
                "trigger": "REALLOCATION_F3"
            })

            send_alert(
                f"🔄 REASIGNACIÓN F3\n"
                f"Vendido: {worst_ticker} ({worst_pnl_pct*100:.1f}%)\n"
                f"Para comprar: {new_ticker} (Votos: {votes}/3)",
                "SELL"
            )
            
            self.sync_balances()

            # Ahora comprar la nueva oportunidad
            buy_amount = min(self.sim_cash, self.MAX_AUTO_USD)
            if buy_amount >= self.MIN_TRADE_USD:
                buy_order = await self.router.execute_market_order(new_ticker, 'buy', buy_amount)
                if buy_order:
                    self.db.update_entry_price(new_ticker, buy_order['price'])
                    self.trades_today += 1
                    send_alert(
                        f"🟢 COMPRA (post-F3)\n"
                        f"{new_ticker} a ${buy_order['price']:.2f}",
                        "BUY"
                    )
                    self.sync_balances()
                    return True

        return False

    # =========================================================================
    # CORTEX ESTRATEGICO — Decision de compra
    # =========================================================================
    async def execute_trade_decision(self, ticker, decision, current_price, votes,
                               is_kamikaze=False, market_prices=None,
                               market_conditions=None):
        """
        Ejecuta la decisión de trading con Gestión de Fees (0.1%) y OCO.
        """
        self.db_positions = self.db.get_all_positions()
        FEE_PCT = 0.001 # 0.1% Binance Standard

        try:
            if not self.router or not self.router.exchange:
                return False

            today = datetime.now().date()
            if self.last_trade_date != today:
                self.trades_today = 0
                self.last_trade_date = today

            qty = self.sim_portfolio.get(ticker, 0.0)

            if decision == "BUY":
                if votes < 2 and not is_kamikaze:
                    return False

                if self.trades_today >= self.MAX_DAILY_TRADES and not is_kamikaze:
                    log.warning(f"[{self.aid}] 🛑 Límite diario alcanzado.")
                    return False

                # Consultar Q-Table antes de comprar
                market_state = market_conditions.get('market_state') if market_conditions else None
                if self.q_table and market_state:
                    q_rec = self.q_table.get_recommendation(market_state)
                    if q_rec['samples'] >= 10 and q_rec['confidence'] < 0.4:
                        log.warning(
                            f"[{self.aid}] [QTABLE] BLOQUEA compra: "
                            f"confianza {q_rec['confidence']:.0%} en este estado"
                        )
                        return False

                # Patrimonio con precios de mercado (FIX-M4)
                if market_prices:
                    valor_activos = sum([
                        q * market_prices.get(t, {}).get('price', 0)
                        for t, q in self.sim_portfolio.items()
                        if t in market_prices
                    ])
                else:
                    valor_activos = sum([
                        q * self.db_positions.get(t, {}).get('entry', current_price)
                        for t, q in self.sim_portfolio.items()
                    ])

                patrimonio = self.sim_cash + valor_activos
                limite_inversion = patrimonio * self.MAX_EXPOSURE

                valor_posicion_actual = qty * current_price
                if valor_posicion_actual >= limite_inversion:
                    return False

                # ¿No hay cash? Intentar Reasignación F3
                if self.sim_cash < self.MIN_TRADE_USD and votes >= 3:
                    return await self._try_reallocate_capital(
                        ticker, current_price, votes, market_prices
                    )

                # Cortocircuito de Liquidez: Si estamos completamente sin fondos para el exchange, abortamos.
                if self.sim_cash < self.MIN_TRADE_USD:
                    return False
                    
                if is_kamikaze:
                    monto_final = min(self.sim_cash, self.KAMIKAZE_LIMIT)
                else:
                    porcentaje_riesgo = 0.35 if votes >= 3 else 0.25
                    inversion_base = self.sim_cash * porcentaje_riesgo
                    monto_final = min(max(inversion_base, self.MIN_TRADE_USD), self.MAX_AUTO_USD)

                monto_final = min(monto_final, limite_inversion - valor_posicion_actual)
                if monto_final > self.sim_cash or monto_final < self.MIN_TRADE_USD:
                    return False

                # --- SLIPPAGE GUARD ---
                avg_exec_price, slippage = self.get_slippage_estimate(ticker, monto_final)
                if slippage > 0.01: # 1% de impacto máximo permitido
                    log.warning(f"[{self.aid}] 🛑 Slippage muy alto ({slippage:.2%}). Abortando.")
                    return False

                log.info(f"[{self.aid}] 🟡 COMPRA: ${monto_final:.2f} en {ticker} (Est. Slippage: {slippage:.2%})...")
                order = await self.router.execute_market_order(ticker, 'buy', monto_final)

                if order:
                    precio_ejecucion = order['price']
                    qty_comprada = order['amount']
                    old_qty = qty
                    old_entry = self.db_positions.get(ticker, {}).get('entry', precio_ejecucion)
                    new_qty = old_qty + qty_comprada
                    nuevo_precio_promedio = (
                        ((old_qty * old_entry) + (qty_comprada * precio_ejecucion)) / new_qty
                    )
                    
                    costo_fees = monto_final * FEE_PCT

                    self.db.update_entry_price(ticker, nuevo_precio_promedio)
                    self.trades_today += 1

                    # --- Lógica OCO (One-Cancels-the-Other) ---
                    # Stop Loss al 5%, Take Profit al 15% (ajustable por ATR)
                    sl_price = precio_ejecucion * (1 - self.TRAILING_STOP_PCT)
                    tp_price = precio_ejecucion * (1 + self.TAKE_PROFIT_PCT)
                    await self.router.execute_oco_order(ticker, 'sell', qty_comprada, sl_price, tp_price)

                    # Registrar gasto si es Kamikaze
                    if is_kamikaze and self.kamikaze:
                        self.kamikaze.register_expense(monto_final)

                    # Guardar estado para Q-Table post-mortem
                    if market_conditions:
                        self._trade_states[ticker] = market_conditions

                    log.info(
                        f"[{self.aid}] 🟢 COMPRA NETA (Fee: ${costo_fees:.4f}): "
                        f"{qty_comprada} {ticker}"
                    )
                    send_alert(
                        f"COMPRA (NETA): {qty_comprada:.6f} {ticker}\n"
                        f"Precio: ${precio_ejecucion:.2f}\n"
                        f"SL: ${sl_price:.2f} | TP: ${tp_price:.2f}",
                        "BUY"
                    )
                    self.sync_balances()
                    return True
                else:
                    log.error(f"[{self.aid}] ❌ Orden rechazada/no llenada.")
                    return False

            return False
        except Exception as e:
            log.error(f"[{self.aid}] Error en ejecución: {e}")
            return False