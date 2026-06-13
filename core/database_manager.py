import sqlite3
import threading
import logging
from datetime import datetime

log = logging.getLogger("EEA-2026")

class DatabaseManager:
    def __init__(self, db_path="eea_core.db"):
        self.db_path = db_path
        self.lock = threading.Lock() 
        self._build_tables()

    def _build_tables(self):
        with self.lock:
            try:
                conn = sqlite3.connect(self.db_path, timeout=20)
                cursor = conn.cursor()
                
                # 🔴 ACTUALIZACIÓN SQL: Añadida columna 'highest_price' para el Trailing Stop
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS entry_prices (
                        ticker TEXT PRIMARY KEY,
                        price REAL NOT NULL,
                        highest_price REAL NOT NULL,
                        last_updated TEXT NOT NULL
                    )
                ''')
                
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS pnl_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        ticker TEXT NOT NULL,
                        qty REAL NOT NULL,
                        entry_price REAL NOT NULL,
                        exit_price REAL NOT NULL,
                        pnl_usd REAL NOT NULL,
                        pnl_pct REAL NOT NULL,
                        trigger_reason TEXT NOT NULL
                    )
                ''')
                conn.commit()
            except Exception as e:
                log.error(f"[DB] Error fatal creando tablas: {e}")
            finally:
                conn.close()

    def get_all_positions(self):
        """Descarga los precios de entrada y el precio máximo alcanzado."""
        positions = {}
        with self.lock:
            try:
                conn = sqlite3.connect(self.db_path, timeout=20)
                cursor = conn.cursor()
                cursor.execute('SELECT ticker, price, highest_price FROM entry_prices')
                for row in cursor.fetchall():
                    positions[row[0]] = {"entry": row[1], "highest": row[2]}
            except Exception as e:
                log.error(f"[DB] Error leyendo posiciones: {e}")
            finally:
                conn.close()
        return positions

    def update_entry_price(self, ticker, price):
        """Registra una compra nueva. El 'highest' inicial es igual al precio de compra."""
        with self.lock:
            try:
                conn = sqlite3.connect(self.db_path, timeout=20)
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                # FIX-M3: MAX preserva la marca de agua del trailing stop durante DCA
                cursor.execute('''
                    INSERT INTO entry_prices (ticker, price, highest_price, last_updated)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(ticker) DO UPDATE SET 
                        price=excluded.price, 
                        highest_price=CASE 
                            WHEN excluded.highest_price > entry_prices.highest_price THEN excluded.highest_price 
                            ELSE entry_prices.highest_price 
                        END,
                        last_updated=excluded.last_updated
                ''', (ticker, price, price, now))
                conn.commit()
            except Exception as e:
                log.error(f"[DB] Error actualizando precio para {ticker}: {e}")
            finally:
                conn.close()

    def get_performance_metrics(self):
        """Calcula métricas de rendimiento desde el historial de P&L."""
        with self.lock:
            try:
                conn = sqlite3.connect(self.db_path, timeout=20)
                cursor = conn.cursor()
                cursor.execute('SELECT pnl_usd, pnl_pct, trigger_reason FROM pnl_history')
                rows = cursor.fetchall()

                if not rows:
                    return {"total_trades": 0, "win_rate": 0, "total_pnl": 0}

                pnls = [r[0] for r in rows]
                wins = [p for p in pnls if p > 0]
                losses = [p for p in pnls if p < 0]

                return {
                    "total_trades": len(rows),
                    "win_rate": round(len(wins) / len(rows) * 100, 1),
                    "total_pnl": round(sum(pnls), 2),
                    "avg_win": round(sum(wins) / max(1, len(wins)), 2),
                    "avg_loss": round(sum(losses) / max(1, len(losses)), 2),
                    "best_trade": round(max(pnls), 2) if pnls else 0,
                    "worst_trade": round(min(pnls), 2) if pnls else 0,
                    "trailing_stops": len([r for r in rows if r[2] == "TRAILING_STOP_WS"]),
                    "take_profits": len([r for r in rows if r[2] == "TAKE_PROFIT_WS"]),
                }
            except Exception as e:
                log.error(f"[DB] Error calculando métricas: {e}")
                return {"total_trades": 0, "error": str(e)}
            finally:
                conn.close()

    def update_highest_price(self, ticker, highest_price):
        """Actualiza la marca de agua del Trailing Stop."""
        with self.lock:
            try:
                conn = sqlite3.connect(self.db_path, timeout=20)
                cursor = conn.cursor()
                cursor.execute('UPDATE entry_prices SET highest_price = ? WHERE ticker = ?', (highest_price, ticker))
                conn.commit()
            except Exception as e:
                log.error(f"[DB] Error actualizando precio máximo para {ticker}: {e}")
            finally:
                conn.close()

    def delete_position(self, ticker):
        """Borra una moneda de la memoria (Útil para la Auditoría y las Ventas)."""
        with self.lock:
            try:
                conn = sqlite3.connect(self.db_path, timeout=20)
                cursor = conn.cursor()
                cursor.execute('DELETE FROM entry_prices WHERE ticker = ?', (ticker,))
                conn.commit()
            except Exception as e:
                pass
            finally:
                conn.close()

    def record_trade_pnl(self, record_dict):
        with self.lock:
            try:
                conn = sqlite3.connect(self.db_path, timeout=20)
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO pnl_history 
                    (timestamp, ticker, qty, entry_price, exit_price, pnl_usd, pnl_pct, trigger_reason)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    record_dict['timestamp'], record_dict['ticker'], record_dict['qty'],
                    record_dict['entry_price'], record_dict['exit_price'],
                    record_dict['pnl_usd'], record_dict['pnl_pct'], record_dict['trigger']
                ))
                conn.commit()
            except Exception as e:
                log.error(f"[DB] Error guardando P&L: {e}")
            finally:
                conn.close()