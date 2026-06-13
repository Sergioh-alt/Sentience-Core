"""
EEA-2026-ANT: core/provider_pool.py
Singleton centralizado para gestionar TODAS las APIs de IA.
Incluye circuit breaker, rate limiting, y selección por peso.
Reemplaza el bloque duplicado en Analyst, Kamikaze, Predictor, Social.
"""
import os
import random
import time
import logging
import requests

log = logging.getLogger("EEA-2026")


class ProviderPool:
    """
    Singleton que gestiona todas las APIs de IA con:
    - Circuit breaker (3 fallos = 5 min de pausa)
    - Rate limiting global (2s mínimo entre llamadas)
    - Selección por peso aleatorio
    """
    _instance = None

    @classmethod
    def get(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.providers = []
        self._failures = {}
        self._last_call = 0
        self._min_interval = 2.0  # Mínimo 2s entre llamadas a cualquier API

        # Añadir Ollama Local (IA en GPU RTX 3060 Ti) con máxima prioridad
        self.providers.append({
            "name": "Ollama-Local",
            "url": "http://127.0.0.1:11434/v1/chat/completions",
            "key": "ollama-local",
            "model": "llama3.2",  # Modelo local recomendado
            "weight": 50  # Peso altísimo para que domine la ejecución
        })

        # Carga todas las claves de todas las APIs
        for i in range(6):
            g = os.getenv(f"GROQ_API_KEY_{i}")
            if g:
                self.providers.append({
                    "name": f"Groq-{i}",
                    "url": "https://api.groq.com/openai/v1/chat/completions",
                    "key": g,
                    "model": "llama-3.3-70b-versatile",
                    "weight": 10
                })
            c = os.getenv(f"CEREBRAS_API_KEY_{i}")
            if c:
                self.providers.append({
                    "name": f"Cerebras-{i}",
                    "url": "https://api.cerebras.ai/v1/chat/completions",
                    "key": c,
                    "model": "llama3.1-8b",
                    "weight": 8
                })
            d = os.getenv(f"DeepSeek_Api_Key_{i}")
            if d:
                self.providers.append({
                    "name": f"DeepSeek-{i}",
                    "url": "https://api.deepseek.com/chat/completions",
                    "key": d,
                    "model": "deepseek-chat",
                    "weight": 5
                })
            gm = os.getenv(f"GEMINI_API_KEY_{i}")
            if gm:
                self.providers.append({
                    "name": f"Gemini-{i}",
                    "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                    "key": gm,
                    "model": "gemini-2.5-flash",
                    "weight": 2
                })

        log.info(f"[ProviderPool] {len(self.providers)} providers cargados")

    def get_provider(self):
        """Devuelve un provider aleatorio excluyendo los que están en circuit break."""
        available = [p for p in self.providers if not self._is_broken(p['name'])]
        if not available:
            # Si todos están rotos, reset completo
            log.warning("[ProviderPool] [WARN] Todos los providers en circuit break. Reseteando.")
            self._failures.clear()
            available = self.providers

        if not available:
            return None

        pesos = [p['weight'] for p in available]
        return random.choices(available, weights=pesos, k=1)[0]

    def call_llm(self, prompt, temperature=0.2, timeout=30):
        """
        Llamada centralizada a LLM con rate limiting y circuit breaker.
        Retorna (provider_name, content) o (None, None) si falla.
        """
        provider = self.get_provider()
        if not provider:
            return None, None

        # Rate limiting global
        elapsed = time.time() - self._last_call
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_call = time.time()

        try:
            headers = {
                "Authorization": f"Bearer {provider['key']}",
                "Content-Type": "application/json"
            }
            data = {
                "model": provider["model"],
                "messages": [{"role": "user", "content": prompt}],
                "temperature": temperature
            }

            response = requests.post(
                provider["url"],
                headers=headers,
                json=data,
                timeout=timeout
            )
            response.raise_for_status()

            content = response.json()["choices"][0]["message"]["content"].strip()
            self._report_success(provider['name'])
            return provider['name'], content

        except requests.exceptions.HTTPError as http_err:
            status_code = http_err.response.status_code
            if status_code in [401, 402]:
                log.error(f"[ProviderPool] ⛔ Provider {provider['name']} DESACTIVADO (Error {status_code}: Llave sin fondos o inválida)")
                # Lo removemos de la lista para que no se use más en esta sesión
                self.providers = [p for p in self.providers if p['name'] != provider['name']]
            else:
                log.warning(f"[ProviderPool] ❌ {provider['name']} falló: {http_err}")
                self._report_failure(provider['name'])
            return None, None
        except Exception as e:
            log.warning(f"[ProviderPool] ❌ {provider['name']} falló: {e}")
            self._report_failure(provider['name'])
            return None, None

    def _report_failure(self, provider_name):
        if provider_name not in self._failures:
            self._failures[provider_name] = {"count": 0, "last": 0}
        self._failures[provider_name]["count"] += 1
        self._failures[provider_name]["last"] = time.time()

    def _report_success(self, provider_name):
        self._failures.pop(provider_name, None)

    def _is_broken(self, name):
        info = self._failures.get(name, {})
        if info.get("count", 0) >= 3:
            if time.time() - info.get("last", 0) < 300:  # 5 min cooldown
                return True
            # Cooldown expirado, dar otra oportunidad
            self._failures.pop(name, None)
        return False

    @property
    def available_count(self):
        return len([p for p in self.providers if not self._is_broken(p['name'])])
