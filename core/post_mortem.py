"""
EEA-2026-ANT: core/post_mortem.py
Post-Mortem Automático — Analiza cada trade cerrado con LLM.
Después de cada venta, registra TODAS las condiciones del momento
y pide al LLM explicar por qué ganó o perdió.
Alimenta la Q-Table y el MemoryVault.
"""
import logging
from datetime import datetime

log = logging.getLogger("EEA-2026")


class PostMortem:
    def __init__(self, provider_pool, memory_vault, q_table=None):
        self.pool = provider_pool
        self.memory = memory_vault
        self.q_table = q_table

    def analyze_closed_trade(self, trade_data, market_conditions):
        """
        Analiza un trade cerrado y extrae lecciones.
        
        Args:
            trade_data: dict con {ticker, entry_price, exit_price, pnl_usd, 
                                  pnl_pct, trigger, qty, timestamp}
            market_conditions: dict con {rsi, macd_dir, fg_value, volume_spike,
                                         mtf_signal, votes, decision_reason}
        """
        ticker = trade_data.get('ticker', '???')
        pnl = trade_data.get('pnl_usd', 0)
        pnl_pct = trade_data.get('pnl_pct', 0)
        trigger = trade_data.get('trigger', 'UNKNOWN')
        entry = trade_data.get('entry_price', 0)
        exit_p = trade_data.get('exit_price', 0)

        success = pnl > 0
        emoji = "🟢" if success else "🔴"

        # Construir contexto para el LLM
        rsi = market_conditions.get('rsi', 'N/A')
        macd = market_conditions.get('macd_dir', 'N/A')
        fg = market_conditions.get('fg_value', 'N/A')
        vol = market_conditions.get('volume_spike', False)
        mtf = market_conditions.get('mtf_signal', 'N/A')
        votes = market_conditions.get('votes', 0)

        prompt = f"""Analiza este trade de criptomonedas y explica en 2-3 oraciones 
por qué {"ganó" if success else "perdió"}. Sé específico y técnico.

TRADE:
- Activo: {ticker}
- Entrada: ${entry:.2f} → Salida: ${exit_p:.2f}
- PnL: ${pnl:.2f} ({pnl_pct:.1f}%)
- Trigger de salida: {trigger}

CONDICIONES AL COMPRAR:
- RSI: {rsi}
- MACD: {macd}
- Fear & Greed: {fg}/100
- Spike de volumen: {"SÍ" if vol else "NO"}
- Multi-timeframe: {mtf}
- Votos a favor: {votes}/3

Responde SOLO con tu análisis técnico. No uses emojis ni saludos."""

        analysis = "Análisis pendiente"
        try:
            if not success:
                prov_name, llm_response = self.pool.call_llm(prompt)
                analysis = llm_response if llm_response else f"Trade fallido por {trigger}"
            else:
                analysis = f"Trade exitoso: ganancia de {pnl_pct:.1f}% por {trigger}."
                
            if not analysis or len(analysis) < 10:
                analysis = f"Trade {'exitoso' if success else 'fallido'}: {trigger} en {ticker}"
        except Exception as e:
            log.warning(f"[PostMortem] LLM falló: {e}")
            analysis = f"Sin análisis LLM. Trade {'exitoso' if success else 'fallido'} por {trigger}"

        # Guardar lección en MemoryVault
        lesson_text = (
            f"{emoji} [{ticker}] PnL: ${pnl:.2f} ({pnl_pct:.1f}%) | "
            f"Trigger: {trigger} | RSI:{rsi} MACD:{macd} FG:{fg} Votes:{votes}/3 | "
            f"Análisis: {analysis[:200]}"
        )

        try:
            self.memory.save_lesson(ticker, trigger, f"${entry:.2f}→${exit_p:.2f}", lesson_text)
        except Exception:
            pass

        # Alimentar Q-Table si tenemos el estado
        market_state = market_conditions.get('market_state', None)
        if self.q_table and market_state:
            self.q_table.record_outcome(market_state, "BUY", success)

        log.info(
            f"[PostMortem] {emoji} {ticker}: ${pnl:.2f} | {analysis[:100]}..."
        )

        return {
            "ticker": ticker,
            "pnl_usd": pnl,
            "success": success,
            "trigger": trigger,
            "analysis": analysis,
            "lesson": lesson_text,
            "timestamp": datetime.now().isoformat()
        }
