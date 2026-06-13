"""
EEA-2026-ANT: core/backtester.py
Motor de Backtesting — Prueba la estrategia contra datos históricos
sin arriesgar dinero real. Simula el comportamiento del Analista +
Trailing Stop + Take Profit.
"""
import logging
import pandas as pd
import pandas_ta as ta
import yfinance as yf
from datetime import datetime

log = logging.getLogger("EEA-2026")


class Backtester:
    def __init__(self):
        self.results = []

    def run(self, ticker="BTC-USD", days=30, initial_cash=100.0,
            trailing_pct=0.05, take_profit_pct=0.15, max_exposure=0.30):
        """
        Simula la estrategia del AnalystAgent (scoring 2/4) contra datos históricos.
        
        Args:
            ticker: Activo a testear
            days: Días de datos históricos
            initial_cash: Capital inicial en USD
            trailing_pct: Porcentaje de trailing stop (0.05 = 5%)
            take_profit_pct: Porcentaje de take profit (0.15 = 15%)
            max_exposure: Máxima exposición por posición (0.30 = 30%)
        
        Returns:
            dict con métricas de rendimiento
        """
        log.info(f"[Backtester] Iniciando backtest: {ticker} | {days}d | ${initial_cash}")

        # Descargar datos históricos
        try:
            df = yf.Ticker(ticker).history(period=f"{days}d", interval="1h")
            if df.empty or len(df) < 30:
                return {"error": f"Datos insuficientes para {ticker}"}
        except Exception as e:
            return {"error": str(e)}

        # Calcular indicadores
        df['RSI_14'] = ta.rsi(df['Close'], length=14)
        macd = ta.macd(df['Close'])
        df['MACD'] = macd['MACD_12_26_9']
        df['MACD_Signal'] = macd['MACDs_12_26_9']
        bb = ta.bbands(df['Close'], length=20)
        df['BB_Lower'] = bb['BBL_20_2.0']
        df['BB_Upper'] = bb['BBU_20_2.0']

        # ATR para volatilidad
        atr = ta.atr(df['High'], df['Low'], df['Close'], length=14)
        df['ATR_14'] = atr

        df.fillna(0, inplace=True)

        # Estado de simulación
        cash = initial_cash
        position_qty = 0.0
        entry_price = 0.0
        highest_price = 0.0
        trades = []

        # Iterar vela por vela
        for i in range(25, len(df)):
            price = float(df.iloc[i]['Close'])
            rsi = float(df.iloc[i]['RSI_14'])
            macd_val = float(df.iloc[i]['MACD'])
            macd_sig = float(df.iloc[i]['MACD_Signal'])
            bb_lower = float(df.iloc[i]['BB_Lower'])
            bb_upper = float(df.iloc[i]['BB_Upper'])

            # ===== SI TENEMOS POSICIÓN: evaluar salida =====
            if position_qty > 0:
                if price > highest_price:
                    highest_price = price

                drawdown = (price - highest_price) / highest_price if highest_price > 0 else 0
                profit = (price - entry_price) / entry_price if entry_price > 0 else 0

                trigger = None
                if drawdown <= -trailing_pct:
                    trigger = "TRAILING_STOP"
                elif profit >= take_profit_pct:
                    trigger = "TAKE_PROFIT"

                if trigger:
                    pnl_usd = (price - entry_price) * position_qty
                    pnl_pct = ((price - entry_price) / entry_price * 100) if entry_price > 0 else 0
                    cash += position_qty * price
                    trades.append({
                        "type": "SELL",
                        "trigger": trigger,
                        "entry": round(entry_price, 2),
                        "exit": round(price, 2),
                        "pnl_usd": round(pnl_usd, 2),
                        "pnl_pct": round(pnl_pct, 2),
                        "timestamp": str(df.index[i])
                    })
                    position_qty = 0
                    entry_price = 0
                    highest_price = 0
                continue

            # ===== SI NO TENEMOS POSICIÓN: evaluar entrada =====
            buy_score = 0
            if rsi < 45:
                buy_score += 1
            if price <= bb_lower * 1.02:
                buy_score += 1
            if macd_val > macd_sig:
                buy_score += 1
            # Simulamos un score social neutral de 0.6
            buy_score += 1  # Social score simulado

            sell_indicators = 0
            if rsi > 70:
                sell_indicators += 1
            if price >= bb_upper * 0.98:
                sell_indicators += 1

            if buy_score >= 2 and sell_indicators == 0:
                # Comprar
                invest_amount = min(cash * 0.25, cash * max_exposure)
                if invest_amount >= 5.0 and invest_amount <= cash:
                    position_qty = invest_amount / price
                    entry_price = price
                    highest_price = price
                    cash -= invest_amount
                    trades.append({
                        "type": "BUY",
                        "trigger": f"SCORE_{buy_score}/4",
                        "price": round(price, 2),
                        "amount_usd": round(invest_amount, 2),
                        "timestamp": str(df.index[i])
                    })

        # Cerrar posición abierta al final
        if position_qty > 0:
            final_price = float(df.iloc[-1]['Close'])
            pnl_usd = (final_price - entry_price) * position_qty
            pnl_pct = ((final_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
            cash += position_qty * final_price
            trades.append({
                "type": "SELL",
                "trigger": "END_OF_DATA",
                "entry": round(entry_price, 2),
                "exit": round(final_price, 2),
                "pnl_usd": round(pnl_usd, 2),
                "pnl_pct": round(pnl_pct, 2),
                "timestamp": str(df.index[-1])
            })

        # Calcular métricas
        sell_trades = [t for t in trades if t['type'] == 'SELL']
        wins = [t for t in sell_trades if t.get('pnl_usd', 0) > 0]
        losses = [t for t in sell_trades if t.get('pnl_usd', 0) < 0]

        total_pnl = sum(t.get('pnl_usd', 0) for t in sell_trades)
        win_rate = (len(wins) / len(sell_trades) * 100) if sell_trades else 0

        results = {
            "ticker": ticker,
            "period_days": days,
            "initial_cash": initial_cash,
            "final_cash": round(cash, 2),
            "return_pct": round(((cash - initial_cash) / initial_cash) * 100, 2),
            "total_trades": len(sell_trades),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": round(win_rate, 1),
            "total_pnl": round(total_pnl, 2),
            "avg_win": round(sum(t['pnl_usd'] for t in wins) / max(1, len(wins)), 2),
            "avg_loss": round(sum(t['pnl_usd'] for t in losses) / max(1, len(losses)), 2),
            "best_trade": round(max((t['pnl_pct'] for t in sell_trades), default=0), 2),
            "worst_trade": round(min((t['pnl_pct'] for t in sell_trades), default=0), 2),
            "trailing_stops": len([t for t in sell_trades if t.get('trigger') == 'TRAILING_STOP']),
            "take_profits": len([t for t in sell_trades if t.get('trigger') == 'TAKE_PROFIT']),
            "trades_detail": trades
        }

        self.results.append(results)

        # Log resumen
        emoji = "🟢" if cash > initial_cash else "🔴"
        log.info(
            f"[Backtester] {emoji} RESULTADO: {ticker} {days}d | "
            f"${initial_cash} → ${cash:.2f} ({results['return_pct']:+.1f}%) | "
            f"Win Rate: {win_rate:.0f}% | Trades: {len(sell_trades)}"
        )

        return results

    def run_multi(self, tickers=None, days=30, initial_cash=100.0):
        """Corre backtest en múltiples activos y devuelve resumen."""
        if tickers is None:
            tickers = ["BTC-USD", "ETH-USD", "DOGE-USD"]

        all_results = []
        for ticker in tickers:
            result = self.run(ticker, days, initial_cash)
            if "error" not in result:
                all_results.append(result)

        if not all_results:
            return {"error": "Ningún backtest completado"}

        # Resumen global
        avg_return = sum(r['return_pct'] for r in all_results) / len(all_results)
        avg_win_rate = sum(r['win_rate'] for r in all_results) / len(all_results)
        total_profitable = len([r for r in all_results if r['return_pct'] > 0])

        summary = {
            "tickers_tested": len(all_results),
            "avg_return_pct": round(avg_return, 2),
            "avg_win_rate": round(avg_win_rate, 1),
            "profitable_tickers": total_profitable,
            "unprofitable_tickers": len(all_results) - total_profitable,
            "individual_results": all_results
        }

        log.info(
            f"[Backtester] RESUMEN MULTI: {len(all_results)} activos | "
            f"Retorno promedio: {avg_return:+.1f}% | Win Rate: {avg_win_rate:.0f}%"
        )
        return summary
