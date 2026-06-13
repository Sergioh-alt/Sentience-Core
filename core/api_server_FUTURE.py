#!/usr/bin/env python3
"""
EEA-2026: core/api_server.py
FastAPI — Puente entre el HUD Next.js y el App Orchestrator.
Endpoints: /api/run, /api/hardware, /api/system, /api/insights,
           /api/debate, /api/mpp, /api/insights/convert, /api/hud (POST)
"""
from __future__ import annotations
import os, json, asyncio
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import asdict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# importar el orquestador
import sys
sys.path.insert(0, str(Path(__file__).parent))
from app_orchestrator import (
    EEA2026Orchestrator, TaskType,
    _SAFE_START, _HW_GOAL, _INCUBATOR, HW_PROFILE,
    get_wr, EEA
)

app = FastAPI(title="EEA-2026 API", version="2.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

_ORCH: Optional[EEA2026Orchestrator] = None
_DEBATE_BUFFER: List[Dict] = []     # últimas entradas de debate
_MPP_BUFFER:    List[Dict] = []     # alertas MPP pendientes

def get_orch() -> EEA2026Orchestrator:
    global _ORCH
    if _ORCH is None: _ORCH = EEA2026Orchestrator()
    return _ORCH

# ── modelos Pydantic ──────────────────────────────────────────────────────

class RunRequest(BaseModel):
    task_type: str = "investment"
    context:   Dict[str,Any] = {}

class HUDEvent(BaseModel):
    type:  str
    alert: Optional[Dict] = None
    goal:  Optional[Dict] = None
    insights: Optional[List] = None

class ConvertRequest(BaseModel):
    id: str

# ── endpoints ─────────────────────────────────────────────────────────────

@app.get("/api/system")
async def system_status():
    orch = get_orch()
    return {
        "safe_start":      _SAFE_START.status(),
        "hw_goal":         _HW_GOAL.status(),
        "pending_insights":len(_INCUBATOR.pending()),
        "hw_profile":      HW_PROFILE,
        "reasoning_mode":  HW_PROFILE.get("reasoning_mode","quantized_q4"),
        "agent_weights":   {k: round(v.weight,3) for k,v in get_wr().w.items()},
    }

@app.get("/api/hardware")
async def hardware_status():
    """Lee el último snapshot del Hardware Monitor si está disponible."""
    snap_path = EEA/"logs"/"hw_latest.json"
    if snap_path.exists():
        try:
            return json.loads(snap_path.read_text())
        except Exception: pass
    # Fallback: leer via psutil directamente
    try:
        import psutil, subprocess
        cpu = psutil.cpu_percent(interval=None)
        vm  = psutil.virtual_memory()
        gpus = []
        try:
            out = subprocess.check_output(
                ["nvidia-smi","--query-gpu=name,temperature.gpu,memory.used,memory.total,utilization.gpu",
                 "--format=csv,noheader,nounits"],timeout=5).decode().strip()
            for line in out.split("\n"):
                p = [x.strip() for x in line.split(",")]
                if len(p)>=5:
                    vram_pct = int(p[2])/int(p[3])*100 if int(p[3])>0 else 0
                    gpus.append({"name":p[0],"temp_c":float(p[1]),"vram_pct":round(vram_pct,1),
                                 "utilization":float(p[4])})
        except Exception: pass
        status="OK"
        if gpus and gpus[0]["temp_c"]>=83: status="PANIC"
        elif gpus and gpus[0]["temp_c"]>=78: status="CRITICAL"
        elif gpus and gpus[0]["vram_pct"]>=90: status="WARNING"
        return {"gpu_name":gpus[0]["name"] if gpus else "CPU","temp_c":gpus[0]["temp_c"] if gpus else 0,
                "vram_pct":gpus[0]["vram_pct"] if gpus else 0,"ram_pct":vm.percent,
                "cpu_pct":cpu,"status":status,"gpus":gpus}
    except Exception as e:
        return {"gpu_name":"—","temp_c":0,"vram_pct":0,"ram_pct":0,"cpu_pct":0,"status":"OK","error":str(e)}

@app.post("/api/run")
async def run_task(req: RunRequest):
    orch = get_orch()
    try:
        task_type = TaskType(req.task_type)
    except ValueError:
        raise HTTPException(400, f"task_type inválido: {req.task_type}")
    # leer hw actual
    hw = await hardware_status()
    result = await orch.run_task(task_type, {"context": req.context, "requirements": {}}, hw=hw)
    # guardar debate en buffer
    if "final_output" in result and result["final_output"]:
        fo = result["final_output"]
        # el debate se extrae del orchestrator interno en producción real;
        # aquí publicamos el postmortem como proxy
        _DEBATE_BUFFER.clear()
    return result

@app.get("/api/insights")
async def get_insights():
    return _INCUBATOR.pending()

@app.post("/api/insights/convert")
async def convert_insight(req: ConvertRequest):
    result = _INCUBATOR.convert_to_task(req.id)
    if not result:
        raise HTTPException(404, "Insight no encontrado")
    # Lanzar como nueva tarea
    orch = get_orch()
    task_type_str = result.get("task_type","investment")
    try: tt = TaskType(task_type_str)
    except ValueError: tt = TaskType.RESEARCH
    hw = await hardware_status()
    task_result = await orch.run_task(tt,
        {"context":{"news":[result["description"]],"requirements":{}},
         "requirements":{"source_insight": req.id}}, hw=hw)
    return {"insight_converted": req.id, "task_result": task_result}

@app.get("/api/debate")
async def get_debate():
    return _DEBATE_BUFFER[-20:] if _DEBATE_BUFFER else []

@app.get("/api/mpp")
async def get_mpp():
    return _MPP_BUFFER[-10:]

@app.post("/api/hud")
async def receive_hud_event(event: HUDEvent):
    """Recibe eventos del sistema (MPP alerts, HW Goal updates, nuevos insights)."""
    if event.type == "MPP_ALERT" and event.alert:
        _MPP_BUFFER.append({**event.alert, "received_at": datetime.now().isoformat()})
        if len(_MPP_BUFFER) > 50: _MPP_BUFFER.pop(0)
    elif event.type == "HW_GOAL_UPDATE" and event.goal:
        pass  # ya actualizado en _HW_GOAL por el tracker
    elif event.type == "NEW_INSIGHTS" and event.insights:
        pass  # ya en _INCUBATOR
    return {"ok": True}

@app.get("/health")
async def health():
    return {"status":"ok","version":"2.1.0","ts":datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api_server:app", host="0.0.0.0", port=8000, reload=False)
