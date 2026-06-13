import json
import logging
from pathlib import Path

log = logging.getLogger("EEA-2026")

class MemoryVault:
    def __init__(self, db_path="memory_db.json"):
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            self.db_path = Path("core/memory_db.json")
        
        # --- LÍMITE EXPANDIDO PARA MAYOR CONTEXTO ---
        self.memory_limit = 200 

    def _load_db(self):
        try:
            if self.db_path.exists():
                with open(self.db_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            log.error(f"Error leyendo memoria: {e}")
        return {"lessons": []}

    def _save_db(self, data):
        try:
            with open(self.db_path, 'w') as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            log.error(f"Error guardando memoria: {e}")

    def save_lesson(self, ticker, decision, outcome, logic):
        db = self._load_db()
        lesson = {
            "ticker": ticker,
            "decision": decision,
            "outcome": outcome,
            "logic": logic
        }
        db["lessons"].append(lesson)
        
        # Sistema de poda automática: Mantiene solo las últimas 200 lecciones
        if len(db["lessons"]) > self.memory_limit:
            db["lessons"] = db["lessons"][-self.memory_limit:]
            
        self._save_db(db)