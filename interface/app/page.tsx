// interface/app/page.tsx
// EEA-2026 HUD — Dashboard principal con:
//   Lego blocks (React Flow), Barra de Metas, Incubadora de Insights,
//   Logs de debate, Monitor de hardware en tiempo real, Safe-Start status

"use client";
import { useState, useEffect, useCallback } from "react";
import {
  Activity, Cpu, MemoryStick, Zap, TrendingUp, Target,
  Lightbulb, Shield, AlertTriangle, CheckCircle2, ArrowRight,
  RefreshCw, Play, Pause, Terminal
} from "lucide-react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── tipos ──────────────────────────────────────────────────────────────────

interface HWStatus { gpu_name:string; temp_c:number; vram_pct:number; ram_pct:number; cpu_pct:number; status:string }
interface SafeStart { mode:string; consecutive_successes:number; required:number; remaining:number; avg_confidence:number; progress_pct:number; production_unlocked:boolean }
interface HWGoal    { goal:string; target:number; current:number; remaining:number; pct:number; unlocked:boolean }
interface Insight   { id:string; category:string; description:string; estimated_value_usd:number|null; efficiency_gain_pct:number|null; confidence:number; status:string; created_at:string }
interface AgentVote { agent:string; confidence:number; weight:number; output:string }
interface MPPAlert  { alert_id:string; level:string; title:string; body:string; options:string[] }

// ── helpers ────────────────────────────────────────────────────────────────

const lvlColor: Record<string,string> = {
  OK:"text-emerald-400", WARNING:"text-amber-400",
  CRITICAL:"text-red-500", PANIC:"text-red-600",
  INFO:"text-sky-400"
};
const catColor: Record<string,string> = {
  financial_arbitrage:"bg-emerald-900 text-emerald-300",
  code_improvement:"bg-violet-900 text-violet-300",
  news_signal:"bg-amber-900 text-amber-300",
  sota_update:"bg-sky-900 text-sky-300",
};
const fmt = (n:number) => n>=1000?`$${(n/1000).toFixed(1)}k`:`$${n.toFixed(0)}`;

// ── hook: polling genérico ─────────────────────────────────────────────────

function usePoll<T>(path:string, fallback:T, interval=3000) {
  const [data, setData] = useState<T>(fallback);
  useEffect(() => {
    const tick = async () => {
      try { const r=await fetch(`${API}${path}`); if(r.ok) setData(await r.json()) }
      catch {}
    };
    tick();
    const id = setInterval(tick, interval);
    return () => clearInterval(id);
  }, [path, interval]);
  return data;
}

// ════════════════════════════════════════════════════════════════════════════
// COMPONENTES
// ════════════════════════════════════════════════════════════════════════════

// ── Barra de Metas de Hardware ────────────────────────────────────────────

function HWGoalBar({ goal }: { goal: HWGoal }) {
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Target size={16} className="text-violet-400" />
          <span className="text-sm font-medium text-slate-200">Meta: {goal.goal}</span>
        </div>
        <span className={`text-xs font-mono ${goal.unlocked ? "text-emerald-400" : "text-slate-400"}`}>
          {goal.unlocked ? "✓ META ALCANZADA" : `${fmt(goal.remaining)} restantes`}
        </span>
      </div>
      <div className="w-full bg-slate-700 rounded-full h-3 overflow-hidden">
        <div
          className={`h-3 rounded-full transition-all duration-700 ${goal.unlocked ? "bg-emerald-500" : "bg-gradient-to-r from-violet-600 to-violet-400"}`}
          style={{ width: `${goal.pct}%` }}
        />
      </div>
      <div className="flex justify-between mt-1 text-xs text-slate-500">
        <span>{fmt(goal.current)}</span>
        <span>{goal.pct.toFixed(1)}%</span>
        <span>{fmt(goal.target)}</span>
      </div>
    </div>
  );
}

// ── Safe-Start Status ─────────────────────────────────────────────────────

function SafeStartPanel({ ss }: { ss: SafeStart }) {
  const isPaper = ss.mode === "paper";
  return (
    <div className={`border rounded-xl p-4 ${isPaper ? "bg-amber-950 border-amber-700" : "bg-emerald-950 border-emerald-700"}`}>
      <div className="flex items-center gap-2 mb-2">
        <Shield size={16} className={isPaper ? "text-amber-400" : "text-emerald-400"} />
        <span className="text-sm font-medium text-slate-200">
          {isPaper ? "Modo Paper Trading" : "✓ Producción Real"}
        </span>
      </div>
      {isPaper && (
        <>
          <div className="w-full bg-slate-700 rounded-full h-2 mb-2 overflow-hidden">
            <div className="h-2 rounded-full bg-amber-500 transition-all duration-500"
                 style={{ width: `${ss.progress_pct}%` }} />
          </div>
          <div className="text-xs text-slate-400">
            {ss.consecutive_successes}/{ss.required} éxitos consecutivos •
            Confianza media: {(ss.avg_confidence*100).toFixed(0)}%
          </div>
        </>
      )}
    </div>
  );
}

// ── Monitor de Hardware ────────────────────────────────────────────────────

function HWMonitor({ hw }: { hw: HWStatus }) {
  const tColor = hw.temp_c >= 83 ? "text-red-500" : hw.temp_c >= 78 ? "text-amber-400" : "text-emerald-400";
  const vColor = hw.vram_pct >= 90 ? "text-red-500" : hw.vram_pct >= 75 ? "text-amber-400" : "text-slate-300";
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-xl p-4">
      <div className="flex items-center gap-2 mb-3">
        <Cpu size={16} className="text-slate-400" />
        <span className="text-xs text-slate-400 truncate">{hw.gpu_name || "GPU"}</span>
        <span className={`ml-auto text-xs font-mono ${lvlColor[hw.status] || "text-slate-400"}`}>
          {hw.status}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-3">
        {[
          { label:"GPU Temp", val:`${hw.temp_c?.toFixed(0) ?? "—"}°C`, color:tColor },
          { label:"VRAM",     val:`${hw.vram_pct?.toFixed(0) ?? "—"}%`, color:vColor },
          { label:"RAM",      val:`${hw.ram_pct?.toFixed(0) ?? "—"}%`,  color:"text-slate-300" },
          { label:"CPU",      val:`${hw.cpu_pct?.toFixed(0) ?? "—"}%`,  color:"text-slate-300" },
        ].map(({ label, val, color }) => (
          <div key={label} className="bg-slate-900 rounded-lg p-2 text-center">
            <div className={`text-base font-mono font-semibold ${color}`}>{val}</div>
            <div className="text-[10px] text-slate-500 mt-0.5">{label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Incubadora de Insights ─────────────────────────────────────────────────

function InsightCard({ insight, onConvert }: { insight: Insight; onConvert: (id:string) => void }) {
  const catClass = catColor[insight.category] || "bg-slate-800 text-slate-300";
  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg p-3 hover:border-slate-500 transition-colors">
      <div className="flex items-start justify-between gap-2 mb-2">
        <span className={`text-[10px] px-2 py-0.5 rounded-full font-medium ${catClass}`}>
          {insight.category.replace("_"," ")}
        </span>
        <span className="text-xs text-slate-400 font-mono">{(insight.confidence*100).toFixed(0)}%</span>
      </div>
      <p className="text-xs text-slate-200 leading-relaxed mb-2">{insight.description}</p>
      <div className="flex items-center gap-3 text-xs text-slate-400 mb-3">
        {insight.estimated_value_usd != null && (
          <span className="flex items-center gap-1 text-emerald-400">
            <TrendingUp size={11} /> {fmt(insight.estimated_value_usd)}
          </span>
        )}
        {insight.efficiency_gain_pct != null && (
          <span className="flex items-center gap-1 text-sky-400">
            <Zap size={11} /> +{insight.efficiency_gain_pct.toFixed(0)}%
          </span>
        )}
      </div>
      <button
        onClick={() => onConvert(insight.id)}
        className="w-full flex items-center justify-center gap-1.5 text-xs bg-violet-700 hover:bg-violet-600 text-white px-3 py-1.5 rounded-lg transition-colors"
      >
        <ArrowRight size={12} /> Convertir en Tarea
      </button>
    </div>
  );
}

function InsightPanel({ insights, onConvert }: { insights:Insight[]; onConvert:(id:string)=>void }) {
  const pending = insights.filter(i => i.status==="pending");
  return (
    <div className="bg-slate-900 border border-slate-700 rounded-xl overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 bg-slate-800 border-b border-slate-700">
        <Lightbulb size={15} className="text-amber-400" />
        <span className="text-sm font-medium text-slate-200">Oportunidades Detectadas</span>
        {pending.length > 0 && (
          <span className="ml-auto bg-amber-500 text-slate-900 text-[10px] font-bold px-2 py-0.5 rounded-full">
            {pending.length}
          </span>
        )}
      </div>
      <div className="p-3 space-y-2 max-h-96 overflow-y-auto">
        {pending.length === 0 ? (
          <p className="text-xs text-slate-500 text-center py-6">El Analista no ha detectado oportunidades aún.</p>
        ) : (
          pending.map(ins => (
            <InsightCard key={ins.id} insight={ins} onConvert={onConvert} />
          ))
        )}
      </div>
    </div>
  );
}

// ── Debate Log ────────────────────────────────────────────────────────────

function DebateLog({ votes }: { votes: AgentVote[] }) {
  const agentColors: Record<string,string> = {
    analyst:"text-sky-400", strategist:"text-violet-400", guardian:"text-red-400",
    risk_manager:"text-orange-400", executor:"text-teal-400", postmortem:"text-slate-400",
    sentinel:"text-pink-400", architect:"text-lime-400",
  };
  return (
    <div className="bg-slate-900 border border-slate-700 rounded-xl overflow-hidden">
      <div className="flex items-center gap-2 px-4 py-3 bg-slate-800 border-b border-slate-700">
        <Terminal size={15} className="text-slate-400" />
        <span className="text-sm font-medium text-slate-200">Debate de Agentes</span>
      </div>
      <div className="p-3 space-y-2 max-h-72 overflow-y-auto font-mono text-xs">
        {votes.length === 0 ? (
          <p className="text-slate-500 text-center py-4">Sin actividad reciente.</p>
        ) : (
          votes.map((v, i) => (
            <div key={i} className="flex gap-2 items-start">
              <span className={`min-w-[90px] ${agentColors[v.agent] || "text-slate-400"}`}>
                [{v.agent}]
              </span>
              <span className="text-slate-500">W={v.weight?.toFixed(2) ?? "?"}</span>
              <span className="text-slate-500">C={((v.confidence||0)*100).toFixed(0)}%</span>
              <span className="text-slate-300 truncate flex-1">{v.output?.slice(0,80)}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// ── MPP Alert Toast ────────────────────────────────────────────────────────

function MPPToast({ alert, onDismiss }: { alert:MPPAlert; onDismiss:()=>void }) {
  const bg = { INFO:"bg-sky-900 border-sky-700", WARNING:"bg-amber-900 border-amber-700",
               CRITICAL:"bg-red-950 border-red-700", PANIC:"bg-red-950 border-red-500" };
  const ico = { INFO:<CheckCircle2 size={16} className="text-sky-400 shrink-0"/>,
                WARNING:<AlertTriangle size={16} className="text-amber-400 shrink-0"/>,
                CRITICAL:<AlertTriangle size={16} className="text-red-400 shrink-0"/>,
                PANIC:<AlertTriangle size={16} className="text-red-500 shrink-0"/> };
  return (
    <div className={`border rounded-xl p-4 ${bg[alert.level as keyof typeof bg] || bg.INFO}`}>
      <div className="flex items-start gap-2">
        {ico[alert.level as keyof typeof ico]}
        <div className="flex-1">
          <p className="text-sm font-medium text-slate-200">{alert.title}</p>
          <p className="text-xs text-slate-400 mt-1">{alert.body}</p>
          {alert.options?.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-3">
              {alert.options.map((opt,i) => (
                <button key={i} onClick={onDismiss}
                  className="text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 px-3 py-1 rounded-lg transition-colors">
                  {opt}
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ════════════════════════════════════════════════════════════════════════════
// PÁGINA PRINCIPAL
// ════════════════════════════════════════════════════════════════════════════

export default function HUDPage() {
  const hw       = usePoll<HWStatus>("/api/hardware",{gpu_name:"—",temp_c:0,vram_pct:0,ram_pct:0,cpu_pct:0,status:"OK"});
  const sysState = usePoll<any>("/api/system",{safe_start:{mode:"paper",consecutive_successes:0,required:10,remaining:10,avg_confidence:0,progress_pct:0,production_unlocked:false},hw_goal:{goal:"RTX 5090",target:2000,current:0,remaining:2000,pct:0,unlocked:false},pending_insights:0,reasoning_mode:"quantized_q4"});
  const insights = usePoll<Insight[]>("/api/insights",[],5000);
  const debate   = usePoll<AgentVote[]>("/api/debate",[],4000);
  const alerts   = usePoll<MPPAlert[]>("/api/mpp",[],2000);

  const [dismissed, setDismissed] = useState<Set<string>>(new Set());
  const [taskForm, setTaskForm] = useState({ type:"investment", news:"" });
  const [running, setRunning] = useState(false);
  const [lastResult, setLastResult] = useState<any>(null);

  const runTask = useCallback(async () => {
    setRunning(true);
    try {
      const res = await fetch(`${API}/api/run`, {
        method:"POST",
        headers:{"Content-Type":"application/json"},
        body: JSON.stringify({ task_type: taskForm.type,
          context: { news: taskForm.news.split("\n").filter(Boolean) } })
      });
      setLastResult(await res.json());
    } catch(e) {
      setLastResult({ error: String(e) });
    } finally {
      setRunning(false);
    }
  }, [taskForm]);

  const convertInsight = useCallback(async (id:string) => {
    await fetch(`${API}/api/insights/convert`, {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({id})});
  }, []);

  const pendingAlerts = alerts.filter(a => !dismissed.has(a.alert_id));

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-4 font-sans">
      {/* ── Header ── */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold tracking-tight">EEA-2026 HUD</h1>
          <p className="text-xs text-slate-400 mt-0.5">
            Motor cognitivo local • Modo: <span className="text-violet-400 font-mono">{sysState.reasoning_mode}</span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${running ? "bg-amber-400 animate-pulse" : "bg-emerald-500"}`} />
          <span className="text-xs text-slate-400">{running ? "Procesando..." : "En espera"}</span>
        </div>
      </div>

      {/* ── MPP Alerts ── */}
      {pendingAlerts.length > 0 && (
        <div className="space-y-2 mb-4">
          {pendingAlerts.slice(0,3).map(a => (
            <MPPToast key={a.alert_id} alert={a} onDismiss={() => setDismissed(s => new Set(s).add(a.alert_id))} />
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* ── Columna izquierda ── */}
        <div className="space-y-4">
          <HWMonitor hw={hw} />
          <HWGoalBar goal={sysState.hw_goal} />
          <SafeStartPanel ss={sysState.safe_start} />

          {/* Lanzar tarea */}
          <div className="bg-slate-800 border border-slate-700 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-3">
              <Play size={15} className="text-emerald-400" />
              <span className="text-sm font-medium text-slate-200">Nueva Tarea</span>
            </div>
            <select
              value={taskForm.type}
              onChange={e => setTaskForm(f=>({...f,type:e.target.value}))}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-sm text-slate-200 mb-2 focus:outline-none focus:border-violet-500"
            >
              <option value="investment">Inversión</option>
              <option value="software">Software</option>
              <option value="research">Investigación</option>
              <option value="self_improve">Auto-Mejora</option>
            </select>
            <textarea
              placeholder="Noticias clave (una por línea)..."
              value={taskForm.news}
              onChange={e => setTaskForm(f=>({...f,news:e.target.value}))}
              className="w-full bg-slate-900 border border-slate-700 rounded-lg px-3 py-2 text-xs text-slate-200 mb-3 h-20 resize-none focus:outline-none focus:border-violet-500"
            />
            <button
              onClick={runTask}
              disabled={running}
              className="w-full flex items-center justify-center gap-2 bg-violet-700 hover:bg-violet-600 disabled:opacity-50 text-white text-sm px-4 py-2 rounded-lg transition-colors"
            >
              {running ? <RefreshCw size={14} className="animate-spin"/> : <Play size={14}/>}
              {running ? "Procesando..." : "Ejecutar"}
            </button>

            {lastResult && (
              <div className="mt-3 bg-slate-900 rounded-lg p-3 text-xs">
                <p className={lastResult.status==="completed" ? "text-emerald-400" : "text-red-400"}>
                  {lastResult.status==="completed" ? "✓ Completada" : "✗ Error"}
                  {lastResult.weighted_consensus && ` · Consenso ${(lastResult.weighted_consensus*100).toFixed(0)}%`}
                  {lastResult.emergency && " · ⚡ EMERGENCIA"}
                </p>
                {lastResult.error && <p className="text-red-400 mt-1">{lastResult.error}</p>}
              </div>
            )}
          </div>
        </div>

        {/* ── Columna central: Debate + Insights ── */}
        <div className="space-y-4">
          <DebateLog votes={debate} />
          <InsightPanel insights={insights} onConvert={convertInsight} />
        </div>

        {/* ── Columna derecha: Pesos de agentes ── */}
        <div className="space-y-4">
          <div className="bg-slate-900 border border-slate-700 rounded-xl overflow-hidden">
            <div className="flex items-center gap-2 px-4 py-3 bg-slate-800 border-b border-slate-700">
              <Activity size={15} className="text-violet-400" />
              <span className="text-sm font-medium text-slate-200">Pesos Históricos (P2)</span>
            </div>
            <div className="p-4 space-y-2">
              {lastResult?.final_output?.postmortem?.agent_weights
                ? Object.entries(lastResult.final_output.postmortem.agent_weights as Record<string,number>).map(([agent, w]) => (
                  <div key={agent} className="flex items-center gap-2">
                    <span className="text-xs text-slate-400 w-24 truncate">{agent}</span>
                    <div className="flex-1 bg-slate-700 rounded-full h-1.5 overflow-hidden">
                      <div className="h-1.5 rounded-full bg-violet-500 transition-all"
                           style={{ width: `${Math.min(100, w*80)}%` }} />
                    </div>
                    <span className="text-xs font-mono text-slate-400 w-8 text-right">{w.toFixed(2)}</span>
                  </div>
                ))
                : <p className="text-xs text-slate-500 text-center py-4">Sin datos aún — ejecuta una tarea.</p>
              }
            </div>
          </div>

          {/* Safe-Start progress detail */}
          <div className="bg-slate-900 border border-slate-700 rounded-xl p-4">
            <div className="flex items-center gap-2 mb-3">
              <Shield size={15} className="text-amber-400" />
              <span className="text-sm font-medium text-slate-200">Progreso Safe-Start</span>
            </div>
            <div className="grid grid-cols-3 gap-2 text-center">
              {[
                {label:"Éxitos consec.",val:sysState.safe_start?.consecutive_successes??0,color:"text-emerald-400"},
                {label:"Necesarios",val:sysState.safe_start?.required??10,color:"text-slate-300"},
                {label:"Confianza",val:`${((sysState.safe_start?.avg_confidence??0)*100).toFixed(0)}%`,color:"text-violet-400"},
              ].map(({label,val,color})=>(
                <div key={label} className="bg-slate-800 rounded-lg p-2">
                  <div className={`text-lg font-mono font-semibold ${color}`}>{val}</div>
                  <div className="text-[10px] text-slate-500">{label}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Info Hardware */}
          <div className="bg-slate-900 border border-slate-700 rounded-xl p-4 text-xs space-y-1">
            <div className="flex items-center gap-2 mb-2">
              <Cpu size={13} className="text-slate-400"/>
              <span className="text-slate-400 font-medium">Perfil de Hardware</span>
            </div>
            {[
              ["GPU",hw.gpu_name||"—"],
              ["VRAM",`${sysState.hw_profile?.vram_gb??0} GB`],
              ["Modo Inferencia",sysState.reasoning_mode||"—"],
              ["RAM",`${sysState.hw_profile?.ram_gb??0} GB`],
            ].map(([k,v])=>(
              <div key={k} className="flex justify-between">
                <span className="text-slate-500">{k}</span>
                <span className="text-slate-300 font-mono truncate max-w-[150px]">{v}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
