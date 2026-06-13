"""
EEA-2026-ANT: core/q_table.py
Motor de Aprendizaje Adaptativo — Q-Table de Reinforcement Learning.
"""
import json
import logging
from pathlib import Path

log = logging.getLogger("EEA-2026")

class QTable:
    def __init__(self, db_path="q_table.json"):
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            self.db_path = Path("core/q_table.json")

        self.learning_rate = 0.15
        self.min_samples = 5
        self.decay_factor = 0.99  # Decaimiento para dar peso a lo más reciente
        self.table = self._load()

    def _load(self):
        try:
            if self.db_path.exists():
                with open(self.db_path, 'r') as f:
                    return json.load(f)
        except Exception as e:
            log.warning(f"[QTable] Error cargando: {e}")
        return {}

    def _save(self):
        try:
            with open(self.db_path, 'w') as f:
                json.dump(self.table, f, indent=2)
        except Exception as e:
            log.error(f"[QTable] Error guardando: {e}")

    @staticmethod
    def discretize_state(rsi, macd_direction, fg_value, volume_spike, hour_utc, whale_score=50, imbalance=1.0):
        """
        Convierte condiciones continuas en un estado discreto.
        Añadido: OrderBook Imbalance (Fase Pro).
        """
        hour_local = (hour_utc - 5) % 24
        
        # RSI
        if rsi < 30: rsi_zone = "RSI_OS"
        elif rsi < 45: rsi_zone = "RSI_LOW"
        elif rsi < 55: rsi_zone = "RSI_NEUTRAL"
        elif rsi < 70: rsi_zone = "RSI_HIGH"
        else: rsi_zone = "RSI_OB"

        # Fear & Greed
        if fg_value < 30: fg_zone = "FG_FEAR"
        elif fg_value < 70: fg_zone = "FG_NEUTRAL"
        else: fg_zone = "FG_GREED"

        # Whale Sentiment
        if whale_score < 40: wh_zone = "WH_BEAR"
        elif whale_score > 60: wh_zone = "WH_BULL"
        else: wh_zone = "WH_NEUT"

        # OrderBook Imbalance
        if imbalance > 1.3: imb_zone = "IMB_BULL"
        elif imbalance < 0.7: imb_zone = "IMB_BEAR"
        else: imb_zone = "IMB_NEUT"

        vol_zone = "VOL_SPIKE" if volume_spike else "VOL_NORMAL"
        
        # Hora
        if 9 <= hour_local <= 15: hz = "NYSE"
        elif 19 <= hour_local <= 23 or 0 <= hour_local <= 2: hz = "ASIA"
        else: hz = "OTHER"

        return f"{rsi_zone}|{macd_direction}|{fg_zone}|{wh_zone}|{imb_zone}|{hz}"

    def get_confidence(self, state, action):
        if state not in self.table: return 0.5
        state_data = self.table[state]
        action_data = state_data.get(action, {"wins": 0.0, "total": 0.0})
        total = action_data.get("total", 0.0)
        if total < self.min_samples: return 0.5
        return round(action_data.get("wins", 0.0) / total, 3)

    def get_recommendation(self, state):
        if state not in self.table: return {"action": "HOLD", "confidence": 0.5, "samples": 0}
        best_action = "HOLD"
        best_conf = 0.5
        best_samples = 0
        for act in ["BUY", "HOLD", "SELL"]:
            c = self.get_confidence(state, act)
            s = self.table[state].get(act, {}).get("total", 0)
            if c > best_conf and s >= self.min_samples:
                best_conf = c
                best_action = act
                best_samples = s
        return {"action": best_action, "confidence": best_conf, "samples": best_samples}

    def record_outcome(self, state, action, success, reward=1.0):
        """
        Registra el resultado con aprendizaje por refuerzo y decaimiento.
        reward: magnitud del acierto/fallo.
        """
        if state not in self.table: self.table[state] = {}
        if action not in self.table[state]:
            self.table[state][action] = {"wins": 0.0, "losses": 0.0, "total": 0.0}
        
        e = self.table[state][action]
        
        # Aplicar decaimiento a la experiencia previa
        e["wins"] *= self.decay_factor
        e["losses"] *= self.decay_factor
        e["total"] *= self.decay_factor
        
        e["total"] += 1
        if success: 
            e["wins"] += reward
        else: 
            e["losses"] += reward
            
        self._save()
        log.info(f"[QTable] [LEARN] {state} | {action} | {'[OK]' if success else '[FAIL]'} (Reward: {reward})")
