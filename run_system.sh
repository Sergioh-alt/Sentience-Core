#!/bin/bash
# ============================================================================
# EEA-2026: run_system.sh
# Script maestro — levanta todo el ecosistema de una sola vez
# ============================================================================

set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EEA_HOME="$HOME/.eea-2026"
LOG_DIR="$EEA_HOME/logs"
RED='\033[0;31m'; GRN='\033[0;32m'; YLW='\033[1;33m'; CYN='\033[0;36m'; BLD='\033[1m'; NC='\033[0m'

ok()  { echo -e "  ${GRN}✓${NC} $1"; }
warn(){ echo -e "  ${YLW}⚠${NC}  $1"; }
inf() { echo -e "  ${CYN}→${NC} $1"; }

echo ""
echo -e "${BLD}${CYN}╔══════════════════════════════════════════════════════╗"
echo -e "║   EEA-2026 — Inicio del Sistema v2.1                ║"
echo -e "╚══════════════════════════════════════════════════════╝${NC}"
echo ""

# ── 0. Verificar .env ──────────────────────────────────────────────────────
if [ ! -f "$ROOT/.env" ]; then
    warn ".env no encontrado — ejecuta primero: python3 setup_eea.py"
    exit 1
fi
source "$ROOT/.env"
ok ".env cargado"

# ── 1. Modo de razonamiento ────────────────────────────────────────────────
MODE="${EEA_REASONING_MODE:-quantized_q4}"
VRAM="${EEA_VRAM_GB:-0}"
echo ""
echo -e "  ${BLD}Hardware:${NC} ${EEA_GPU_NAME:-Unknown} | ${VRAM}GB VRAM | Modo: ${MODE}"

if (( $(echo "$VRAM >= 24" | bc -l 2>/dev/null || echo 0) )); then
    echo -e "  ${GRN}✓ FULL REASONING activado (VRAM ≥ 24GB)${NC}"
elif (( $(echo "$VRAM >= 12" | bc -l 2>/dev/null || echo 0) )); then
    echo -e "  ${YLW}⚠ Modo Q4 (12 ≤ VRAM < 24GB)${NC}"
else
    echo -e "  ${YLW}⚠ Modo Q3+CPU (VRAM < 12GB) — rendimiento reducido${NC}"
fi

# ── 2. Activar entorno virtual ─────────────────────────────────────────────
VENV="$ROOT/.venv"
if [ -f "$VENV/bin/activate" ]; then
    source "$VENV/bin/activate"
    ok "Entorno virtual activado"
else
    warn "Virtualenv no encontrado — usando Python del sistema"
fi

# ── 3. Servicios Docker ────────────────────────────────────────────────────
echo ""
inf "Verificando servicios Docker..."
if command -v docker &>/dev/null && [ -f "$ROOT/docker-compose.yml" ]; then
    DC=$(docker compose version &>/dev/null 2>&1 && echo "docker compose" || echo "docker-compose")
    $DC -f "$ROOT/docker-compose.yml" up -d --quiet-pull 2>/dev/null || true
    ok "PostgreSQL, ChromaDB, n8n, Redis levantados"
else
    warn "Docker no disponible — bases de datos en modo archivo"
fi

# ── 4. Ollama ──────────────────────────────────────────────────────────────
echo ""
inf "Verificando Ollama..."
if command -v ollama &>/dev/null; then
    # Asegurarse de que ollama serve está corriendo
    if ! curl -s http://localhost:11434/api/tags &>/dev/null; then
        nohup ollama serve > "$LOG_DIR/ollama.log" 2>&1 &
        sleep 3
        ok "Ollama serve iniciado (PID $!)"
    else
        ok "Ollama ya está corriendo"
    fi
else
    warn "Ollama no disponible — modelos LLM no operativos"
fi

# ── 5. Hardware Monitor (background) ──────────────────────────────────────
echo ""
inf "Iniciando Hardware Monitor..."
if [ -f "$ROOT/Hardware_Monitor.py" ]; then
    nohup python3 "$ROOT/Hardware_Monitor.py" > "$LOG_DIR/hw_monitor.log" 2>&1 &
    HW_PID=$!
    ok "Hardware Monitor activo (PID $HW_PID)"
else
    warn "Hardware_Monitor.py no encontrado"
fi

# ── 6. API Backend (FastAPI) ───────────────────────────────────────────────
echo ""
inf "Iniciando API Backend (FastAPI puerto 8000)..."
nohup python3 "$ROOT/core/api_server.py" > "$LOG_DIR/api.log" 2>&1 &
API_PID=$!
sleep 2

if curl -s http://localhost:8000/health &>/dev/null; then
    ok "API Backend activa (PID $API_PID) → http://localhost:8000"
else
    warn "API Backend iniciando... revisar $LOG_DIR/api.log"
fi

# ── 7. Frontend Next.js ────────────────────────────────────────────────────
echo ""
inf "Iniciando Frontend HUD (Next.js puerto 3000)..."
IFACE="$ROOT/interface"
if [ -d "$IFACE" ] && command -v node &>/dev/null; then
    nohup npm --prefix "$IFACE" run dev > "$LOG_DIR/frontend.log" 2>&1 &
    FE_PID=$!
    sleep 4
    if curl -s http://localhost:3000 &>/dev/null; then
        ok "HUD activo (PID $FE_PID) → http://localhost:3000"
    else
        warn "HUD iniciando... revisar $LOG_DIR/frontend.log"
    fi
else
    warn "Node.js no disponible o interface/ no encontrada"
fi

# ── RESUMEN ────────────────────────────────────────────────────────────────
echo ""
echo -e "${BLD}${CYN}╔══════════════════════════════════════════════════════╗"
echo -e "║   SISTEMA ACTIVO                                     ║"
echo -e "╚══════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${GRN}HUD (interfaz):${NC}  http://localhost:3000"
echo -e "  ${GRN}API Backend:${NC}     http://localhost:8000/docs"
echo -e "  ${GRN}n8n Workflows:${NC}   http://localhost:5678"
echo ""
echo -e "  Modo:        ${CYN}${MODE}${NC}"
echo -e "  Safe-Start:  ${YLW}Paper Trading${NC} (hasta 10 éxitos consecutivos)"
echo ""
echo -e "  ${RED}Detención de emergencia:${NC} bash panic_kill.sh"
echo -e "  ${YLW}Logs:${NC} $LOG_DIR/"
echo ""

# Guardar PIDs para detención ordenada
cat > "$EEA_HOME/pids.txt" << PID
API_PID=${API_PID:-0}
FE_PID=${FE_PID:-0}
HW_PID=${HW_PID:-0}
PID

# Mantener script activo (útil para docker / supervisord)
if [ "${1:-}" = "--foreground" ]; then
    echo "Ejecutando en foreground — Ctrl+C para detener"
    wait
fi
