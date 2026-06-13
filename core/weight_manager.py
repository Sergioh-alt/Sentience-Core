"""
EEA-2026-ANT: core/weight_manager.py
Gestor de Pesos de Votación — Reinforcement Loop v1.5.
Ajusta la importancia de cada agente basándose en su precisión histórica.
"""
import json
import logging
from pathlib import Path

log = logging.getLogger("EEA-2026")

class WeightManager:
    def __init__(self, db_path="core/agent_weights.json"):
        self.db_path = Path(db_path)
        # Pesos iniciales equilibrados
        self.default_weights = {
            "analyst": 1.0,
            "predictor": 1.0,
            "whale": 1.2,      # La ballena tiene un poco más de peso inicial
            "technical": 1.0,
            "arbitrage": 0.5
        }
        self.weights = self._load()
        self.learning_rate = 0.05

    def _load(self):
        try:
            if self.db_path.exists():
                with open(self.db_path, 'r') as f:
                    return json.load(f)
        except Exception:
            pass
        return self.default_weights.copy()

    def _save(self):
        try:
            with open(self.db_path, 'w') as f:
                json.dump(self.weights, f, indent=2)
        except Exception as e:
            log.error(f"[WeightManager] Error guardando: {e}")

    def update_weights_from_pnl(self, votes_cast, success):
        """
        Ajusta los pesos de los agentes que votaron.
        votes_cast: list de strings (nombres de agentes que votaron a favor)
        success: bool (si el trade fue exitoso)
        """
        for agent in votes_cast:
            if agent in self.weights:
                if success:
                    # Incrementar peso si el voto fue correcto
                    self.weights[agent] = round(self.weights[agent] + self.learning_rate, 2)
                else:
                    # Penalizar peso si el voto llevó a una pérdida
                    self.weights[agent] = round(max(0.1, self.weights[agent] - self.learning_rate), 2)
        
        # Normalizar para que no exploten los valores
        avg = sum(self.weights.values()) / len(self.weights)
        for k in self.weights:
            self.weights[k] = round(self.weights[k] / avg, 2)
            
        self._save()
        log.info(f"[WeightManager] Pesos actualizados: {self.weights}")

    def get_weight(self, agent_name):
        return self.weights.get(agent_name, 1.0)
