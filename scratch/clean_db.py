import sqlite3
import os

db_path = r"d:\EEA_2026_ANT_LLM\eea_core.db"
print(f"Limpiando DB: {db_path}")

try:
    if os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("DELETE FROM entry_prices;")
        conn.commit()
        conn.close()
        print("✅ Base de datos limpiada. Posiciones fantasmas eliminadas.")
    else:
        print("La base de datos no existe aún.")
except Exception as e:
    print(f"Error: {e}")
