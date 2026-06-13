#!/usr/bin/env python3
"""
EEA-2026 — setup_eea.py
Instalador maestro de un solo clic.
Detecta hardware, instala dependencias, configura DBs, genera .env.
"""
from __future__ import annotations
import os, sys, json, subprocess, platform, shutil, time
from pathlib import Path

# ── colores ──────────────────────────────────────────────────────────────────
R="\033[0;31m"; G="\033[0;32m"; Y="\033[1;33m"; C="\033[0;36m"; B="\033[1m"; N="\033[0m"
def ok(m):  print(f"  {G}✓{N} {m}")
def warn(m):print(f"  {Y}⚠{N}  {m}")
def err(m): print(f"  {R}✗{N} {m}"); sys.exit(1)
def inf(m): print(f"  {C}→{N} {m}")
def hdr(m): print(f"\n{B}{C}━━━ {m} ━━━{N}")

print(f"""
{B}{C}╔══════════════════════════════════════════════════════╗
║   EEA-2026 — Instalador Maestro v2.0                 ║
║   Sistema Operativo Cognitivo Local                  ║
╚══════════════════════════════════════════════════════╝{N}
""")

BASE = Path(__file__).parent
EEA  = Path.home() / ".eea-2026"
for d in ["logs","memory/chroma","sandbox","staging","snapshots","config"]:
    (EEA/d).mkdir(parents=True, exist_ok=True)

# ════════════════════════════════════════════════════════
# 1. DETECCIÓN DE HARDWARE
# ════════════════════════════════════════════════════════
hdr("DETECCIÓN DE HARDWARE")

hw = {"vram_gb": 0, "gpu_name": "CPU-only", "ram_gb": 0, "os": platform.system(),
      "reasoning_mode": "quantized", "vram_tier": "low"}

# RAM
try:
    import psutil
    hw["ram_gb"] = round(psutil.virtual_memory().total / 1e9, 1)
    ok(f"RAM: {hw['ram_gb']} GB")
except ImportError:
    warn("psutil no instalado aún — se instalará ahora")

# GPU vía nvidia-smi
try:
    out = subprocess.check_output(
        ["nvidia-smi","--query-gpu=name,memory.total","--format=csv,noheader,nounits"],
        timeout=8, stderr=subprocess.DEVNULL).decode().strip().split("\n")[0]
    name, vram_mb = [x.strip() for x in out.split(",")]
    hw["vram_gb"]  = round(int(vram_mb)/1024, 1)
    hw["gpu_name"] = name
    ok(f"GPU: {name} — {hw['vram_gb']} GB VRAM")
except Exception:
    # Apple Silicon
    if platform.system()=="Darwin" and platform.machine()=="arm64":
        hw["gpu_name"] = "Apple Silicon (Unified)"
        hw["vram_gb"]  = round(hw.get("ram_gb",0)*0.5, 1)
        ok(f"GPU: Apple Silicon — {hw['vram_gb']} GB unified")
    else:
        warn("GPU no detectada — modo CPU")

# Determinar modo de razonamiento (P1: VRAM gate)
if hw["vram_gb"] >= 24:
    hw["reasoning_mode"] = "full_reasoning"
    hw["vram_tier"]      = "high"
    ok(f"Modo: FULL REASONING (VRAM {hw['vram_gb']} GB ≥ 24 GB)")
elif hw["vram_gb"] >= 12:
    hw["reasoning_mode"] = "quantized_q4"
    hw["vram_tier"]      = "mid"
    ok(f"Modo: CUANTIZADO Q4 (VRAM {hw['vram_gb']} GB ≥ 12 GB)")
else:
    hw["reasoning_mode"] = "quantized_q3_cpu"
    hw["vram_tier"]      = "low"
    warn(f"Modo: Q3 + CPU OFFLOAD (VRAM {hw['vram_gb']} GB < 12 GB)")

# Guardar perfil de hardware
hw_path = EEA / "config" / "hardware_profile.json"
hw_path.write_text(json.dumps(hw, indent=2))
ok(f"Perfil guardado: {hw_path}")

# ════════════════════════════════════════════════════════
# 2. PYTHON Y VIRTUALENV
# ════════════════════════════════════════════════════════
hdr("ENTORNO PYTHON")

VENV = BASE / ".venv"
py = sys.executable
if not VENV.exists():
    inf("Creando entorno virtual...")
    subprocess.run([py, "-m", "venv", str(VENV)], check=True)
    ok("Entorno virtual creado")

PY = str(VENV/"bin"/"python") if (VENV/"bin"/"python").exists() else str(VENV/"Scripts"/"python.exe")
PIP = str(VENV/"bin"/"pip")   if (VENV/"bin"/"pip").exists()    else str(VENV/"Scripts"/"pip.exe")

inf("Instalando dependencias Python...")
deps = [
    "langgraph>=0.2.0","langchain>=0.3.0","langchain-ollama>=0.2.0","langchain-core>=0.3.0",
    "chromadb>=0.5.0","psycopg2-binary>=2.9.0","sentence-transformers>=3.0.0",
    "psutil>=6.0.0","requests>=2.32.0","httpx>=0.28.0","numpy>=1.26.0",
    "fastapi>=0.115.0","uvicorn>=0.32.0","websockets>=13.0","python-dotenv>=1.0.0","pyyaml>=6.0",
]
subprocess.run([PIP,"install","--quiet","--upgrade","pip"]+deps, check=True)
ok("Dependencias Python instaladas")

# ════════════════════════════════════════════════════════
# 3. NODE.JS / FRONTEND
# ════════════════════════════════════════════════════════
hdr("NODE.JS / FRONTEND")

if shutil.which("node"):
    v = subprocess.check_output(["node","--version"],text=True).strip()
    ok(f"Node.js {v}")
    if shutil.which("npm"):
        inf("Instalando dependencias frontend...")
        fe_dir = BASE/"interface"
        if (fe_dir/"package.json").exists():
            subprocess.run(["npm","install","--silent"], cwd=fe_dir, check=True)
            ok("Frontend instalado")
        else:
            warn("package.json no encontrado — saltar npm install")
else:
    warn("Node.js no encontrado. Instala desde https://nodejs.org")
    warn("El frontend no estará disponible hasta que lo instales.")

# ════════════════════════════════════════════════════════
# 4. DOCKER + SERVICIOS
# ════════════════════════════════════════════════════════
hdr("SERVICIOS DOCKER")

if shutil.which("docker"):
    dc_cmd = "docker compose" if subprocess.run(["docker","compose","version"],
                capture_output=True).returncode==0 else "docker-compose"
    inf("Levantando servicios (PostgreSQL, ChromaDB, n8n, Redis)...")
    dc_file = BASE/"docker-compose.yml"
    if dc_file.exists():
        subprocess.run(dc_cmd.split()+["up","-d","--quiet-pull"], cwd=BASE, check=False)
        time.sleep(3)
        ok("Servicios Docker levantados")
    else:
        warn("docker-compose.yml no encontrado — generando...")
        _write_docker_compose(BASE)
        subprocess.run(dc_cmd.split()+["up","-d","--quiet-pull"], cwd=BASE, check=False)
else:
    warn("Docker no disponible — bases de datos en modo archivo")

# ════════════════════════════════════════════════════════
# 5. OLLAMA + MODELOS (SEGÚN VRAM)
# ════════════════════════════════════════════════════════
hdr("MODELOS DE INFERENCIA")

if shutil.which("ollama"):
    # Asegurar que ollama serve esté corriendo
    subprocess.Popen(["ollama","serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)

    MODEL_MAP = {
        "full_reasoning":   ("deepseek-r1:70b-llama-q4_K_M", "llama2:70b-chat-q4_K_M", "phi:3b-instruct-q4"),
        "quantized_q4":     ("deepseek-r1:70b-llama-q4_K_M", "llama2:70b-chat-q4_K_M", "phi:3b-instruct-q4"),
        "quantized_q3_cpu": ("deepseek-r1:7b",                "mistral:7b",               "phi:3b-instruct-q4"),
    }
    mode = hw["reasoning_mode"]
    models = MODEL_MAP.get(mode, MODEL_MAP["quantized_q3_cpu"])
    inf(f"Modo {mode} → modelos: {models}")

    for model in models:
        yn = input(f"  ¿Descargar {model}? [s/N] ").strip().lower()
        if yn in ("s","y","si","yes"):
            subprocess.run(["ollama","pull", model])
            ok(f"{model} descargado")
        else:
            warn(f"{model} omitido")
else:
    warn("Ollama no instalado → https://ollama.ai")

# ════════════════════════════════════════════════════════
# 6. GENERAR .env
# ════════════════════════════════════════════════════════
hdr("CONFIGURACIÓN .ENV")

mode = hw["reasoning_mode"]
MODEL_HEAVY   = "deepseek-r1:70b-llama-q4_K_M" if mode!="quantized_q3_cpu" else "deepseek-r1:7b"
MODEL_CODE    = "llama2:70b-chat-q4_K_M"        if mode!="quantized_q3_cpu" else "mistral:7b"
MODEL_GUARDIAN= "phi:3b-instruct-q4"

env = f"""# EEA-2026 — Variables de entorno generadas automáticamente
# Edita con tus credenciales reales

# ── Hardware ──────────────────────────────────────────
EEA_REASONING_MODE={mode}
EEA_VRAM_GB={hw['vram_gb']}
EEA_GPU_NAME={hw['gpu_name']}

# ── Modelos ───────────────────────────────────────────
OLLAMA_URL=http://localhost:11434
VLLM_URL=http://localhost:8000
MODEL_HEAVY={MODEL_HEAVY}
MODEL_CODE={MODEL_CODE}
MODEL_GUARDIAN={MODEL_GUARDIAN}

# ── Bases de datos ────────────────────────────────────
POSTGRES_HOST=localhost
POSTGRES_USER=aap_user
POSTGRES_PASSWORD=aap_secure_password
POSTGRES_DB=aap_2026_db
CHROMADB_HOST=localhost
CHROMADB_PORT=8080

# ── Servicios ────────────────────────────────────────
N8N_WEBHOOK=http://localhost:5678/webhook/eea-2026
HUD_WS_URL=http://localhost:3000/api/hud
NEXT_PUBLIC_API_URL=http://localhost:8000

# ── Seguridad ────────────────────────────────────────
MAX_SPEND_USD=500.0
MAX_DRAWDOWN_PCT=10.0
GPU_TEMP_LIMIT_C=83
GPU_TEMP_THROTTLE_C=78

# ── Safe-Start (Paper Trading) ───────────────────────
SAFE_START_MODE=true
SAFE_START_MIN_SUCCESSES=10
SAFE_START_MIN_CONFIDENCE=0.65

# ── APIs externas (añade tus keys) ───────────────────
ALPACA_API_KEY=
ALPACA_SECRET_KEY=
BINANCE_API_KEY=
"""
env_path = BASE/".env"
env_path.write_text(env)
ok(f".env generado: {env_path}")

# ════════════════════════════════════════════════════════
# 7. GENERAR panic_kill.sh
# ════════════════════════════════════════════════════════
hdr("SCRIPT DE PÁNICO")
panic = BASE/"panic_kill.sh"
panic.write_text("""#!/bin/bash
REASON="${1:-desconocida}"; TS=$(date '+%Y-%m-%d %H:%M:%S')
echo "[$TS] PANIC KILL — $REASON" >> ~/.eea-2026/logs/panic.log
pkill -f "app_orchestrator" && echo "✓ Orchestrator detenido"
pkill -f "ollama" && echo "✓ Ollama detenido"
pkill -f "vllm"   && echo "✓ vLLM detenido"
docker stop $(docker ps -q --filter label=eea2026) 2>/dev/null && echo "✓ Containers detenidos"
echo "Sistema detenido de forma segura. Razón: $REASON"
""")
panic.chmod(0o755)
ok("panic_kill.sh generado")

# ════════════════════════════════════════════════════════
# RESUMEN FINAL
# ════════════════════════════════════════════════════════
print(f"""
{B}{C}╔══════════════════════════════════════════════════════╗
║   INSTALACIÓN COMPLETADA                             ║
╚══════════════════════════════════════════════════════╝{N}

  GPU: {hw['gpu_name']} ({hw['vram_gb']} GB) → Modo: {hw['reasoning_mode']}
  RAM: {hw['ram_gb']} GB

  {G}Para iniciar el sistema:{N}
  
    bash run_system.sh

  {G}Para detención de emergencia:{N}
    
    bash panic_kill.sh
""")

def _write_docker_compose(base: Path):
    (base/"docker-compose.yml").write_text("""version: '3.9'
services:
  postgres:
    image: postgres:16-alpine
    container_name: eea2026_postgres
    labels: ["eea2026=true"]
    environment: {POSTGRES_USER: aap_user, POSTGRES_PASSWORD: aap_secure_password, POSTGRES_DB: aap_2026_db}
    volumes: [eea_pg:/var/lib/postgresql/data]
    ports: ["5432:5432"]
    restart: unless-stopped
  chromadb:
    image: chromadb/chroma:latest
    container_name: eea2026_chroma
    labels: ["eea2026=true"]
    volumes: [eea_chroma:/chroma/chroma]
    ports: ["8080:8000"]
    restart: unless-stopped
  n8n:
    image: n8nio/n8n:latest
    container_name: eea2026_n8n
    labels: ["eea2026=true"]
    ports: ["5678:5678"]
    volumes: [eea_n8n:/home/node/.n8n]
    restart: unless-stopped
  redis:
    image: redis:7-alpine
    container_name: eea2026_redis
    labels: ["eea2026=true"]
    ports: ["6379:6379"]
    restart: unless-stopped
volumes: {eea_pg: {}, eea_chroma: {}, eea_n8n: {}}
networks:
  default:
    name: eea2026_network
""")
