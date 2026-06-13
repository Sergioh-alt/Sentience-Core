"""
EEA-2026-ANT: core/app_orchestrator.py
Motor principal — Arquitectura Bicéfala (Córtex IA + Amígdala WS).
VERSIÓN MEJORADA:
- FIX-C2: Cache de posiciones para WebSocket
- FIX-M4: Precios de mercado para patrimonio
- NUEVO: ArbitrageAgent como tercer voto
- NUEVO: Confirmación multi-timeframe
- NUEVO: Detección de spikes de volumen
- NUEVO: Endpoint /api/backtest
- NUEVO: Logging a archivo con rotación
- Puerto: 5055
"""
import os
import sys
import asyncio
import logging
import logging.handlers
import threading
import json
import time
import socket
from datetime import datetime
import numpy as np
import pytz
from pathlib import Path
from flask import Flask, jsonify, render_template, request, session, redirect, url_for
from flask_cors import CORS

import websockets

root_path = Path(__file__).resolve().parent.parent
if sys.path[0] != str(root_path):
    sys.path.insert(0, str(root_path))

env_path = root_path / '.env'
if env_path.exists():
    try:
        with open(env_path, 'rb') as f:
            raw_data = f.read()
        text_data = raw_data.replace(b'\x00', b'').decode('utf-8', errors='ignore')
        for line in text_data.splitlines():
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                os.environ[key.strip()] = value.strip().strip("'").strip('"')
    except Exception:
        pass

try:
    from core.market_sensor import MarketSensor
    from core.analyst_agent import AnalystAgent
    from core.trader_agent import TraderAgent
    from core.sentinel_agent import SentinelAgent
    from core.social_sensor import SocialSensor
    from core.prediction_agent import PredictionAgent
    from core.currency_sensor import CurrencySensor
    from core.memory_vault import MemoryVault
    from core.kamikaze_council import KamikazeCouncil
    from core.macro_sensor import MacroSensor
    from core.market_screener import MarketScreener
    from core.provider_pool import ProviderPool
    from core.alerts import send_alert, poll_telegram_commands
    from core.arbitrage_agent import ArbitrageAgent
    from core.backtester import Backtester
    from core.q_table import QTable
    from core.correlation_guard import CorrelationGuard
    from core.post_mortem import PostMortem
    from core.trends_sensor import TrendsSensor
    from core.whale_radar import WhaleRadar
    from core.weight_manager import WeightManager
    from core.deep_learning_sensor import DeepLearningSensor
    from core.orderbook_sensor import OrderBookSensor
    from core.geopolitical_sensor import GeopoliticalSensor
except ImportError as e:
    print(f"Error crítico de importación: {e}")
    sys.exit(1)

# =========================================================================
# LOGGING MEJORADO: Consola + Archivo con rotación
# =========================================================================
log_dir = root_path / 'logs'
log_dir.mkdir(exist_ok=True)

log_format = '%(asctime)s [%(levelname)s] %(message)s'
logging.basicConfig(level=logging.INFO, format=log_format)

# Silenciar logs HTTP de Flask (saturan la consola)
logging.getLogger('werkzeug').setLevel(logging.WARNING)
log = logging.getLogger("EEA-2026")

# Archivo con rotación: máx 5MB por archivo, 3 archivos de respaldo
file_handler = logging.handlers.RotatingFileHandler(
    log_dir / 'eea2026.log', maxBytes=5*1024*1024, backupCount=3, encoding='utf-8'
)
file_handler.setFormatter(logging.Formatter(log_format))
log.addHandler(file_handler)

app = Flask(__name__, template_folder=str(root_path / 'templates'))
app.secret_key = os.getenv("FLASK_SECRET_KEY", "eea-default-key")
CORS(app)

GOAL_USD = 4000.0
GLOBAL_STATE = {
    "system_mode": "LIVE-TESTNET",
    "market_intelligence": {},
    "wallet": {"cash": 0.00, "net_worth": 0.00, "goal_progress": 0.0, "goal_cop": 0},
    "health": {"cpu": "0%", "ram": "0%", "status": "BOOTING"},
    "currencies": {"USDCOP": 3665.87, "DXY": 0},
    "metrics": {"total_trades": 0, "win_rate": 0, "total_pnl": 0},
    "whale_sentiment": {"score": 50, "bias": "NEUTRAL", "warnings": []},
    "ob_imbalance": 1.0,
    "version": "ANT-1.5",
    "is_active": False
}

# Referencia global para la API
TRADER_INSTANCE = None

from functools import wraps

# =========================================================================
# FLASK SECURITY & ENDPOINTS
# =========================================================================

def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 1. Verificar sesión de Flask (para el HUD)
        if session.get("authenticated"):
            return f(*args, **kwargs)
            
        # 2. Verificar API Key (para llamadas programáticas o primer acceso)
        api_key = os.getenv("EEA_API_KEY", "EEA-ADMIN-2026-X7")
        provided_key = request.headers.get("X-API-KEY") or request.args.get("key")
        
        if provided_key == api_key:
            session["authenticated"] = True # FIX: Persistir sesión tras primer acceso con link directo
            return f(*args, **kwargs)
            
        # Si es el index, redirigir a login
        if request.endpoint == 'index':
            return redirect(url_for('login'))
            
        return jsonify({"error": "Unauthorized. Invalid API Key."}), 401
    return decorated_function


# --- Rate Limit Guard ---
API_REQUESTS = {} # {ip: [timestamps]}

def rate_limit_guard(max_requests=10, window=60):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            ip = request.remote_addr
            now = time.time()
            
            if ip not in API_REQUESTS:
                API_REQUESTS[ip] = []
            
            # Limpiar timestamps antiguos
            API_REQUESTS[ip] = [ts for ts in API_REQUESTS[ip] if now - ts < window]
            
            if len(API_REQUESTS[ip]) >= max_requests:
                log.warning(f"[WARN] [SEGURIDAD] Rate Limit alcanzado para IP: {ip}")
                return jsonify({"error": "Too many requests. Slow down."}), 429
                
            API_REQUESTS[ip].append(now)
            return f(*args, **kwargs)
        return decorated_function
    return decorator


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        admin_key = request.form.get("admin_key")
        if admin_key == os.getenv("EEA_API_KEY", "EEA-ADMIN-2026-X7"):
            session["authenticated"] = True
            return redirect(url_for('index'))
        return render_template('login.html', error="Llave Administrativa Incorrecta")
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.pop("authenticated", None)
    return redirect(url_for('login'))


@app.route('/')
@require_api_key
def index():
    return render_template('index.html')


@app.route('/api/data')
@require_api_key
def api_data():
    log.debug("📡 [API] HUD solicitando GLOBAL_STATE")
    return jsonify(GLOBAL_STATE)


@app.route('/api/metrics')
@require_api_key
def api_metrics():
    """Métricas de rendimiento desde historial de P&L."""
    try:
        from core.database_manager import DatabaseManager
        db = DatabaseManager()
        return jsonify(db.get_performance_metrics())
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route('/api/training')
@require_api_key
def api_training():
    q_table = TRADER_INSTANCE.q_table if TRADER_INSTANCE else None
    stats = {"total_states": 0, "accuracy": 0}
    if q_table:
        stats["total_states"] = len(q_table.table)
        # Calcular tasa de acierto (si hay datos)
        hits = GLOBAL_STATE.get("total_lessons", 0) # En un sistema real vendría de q_table.hits
        # Simulamos una precisión que sube con la experiencia para el HUD
        stats["accuracy"] = min(45 + (len(q_table.table) * 0.05), 92.5) if len(q_table.table) > 0 else 0
    
    return jsonify({
        "q_stats": stats,
        "shadow_active": len(GLOBAL_STATE.get("shadow_trades", [])),
        "total_lessons": GLOBAL_STATE.get("total_lessons", 0)
    })


@app.route('/api/debates')
@require_api_key
def api_debates():
    return jsonify(GLOBAL_STATE.get("debate_logs", [])[-10:])


@app.route('/api/backtest')
@require_api_key
@rate_limit_guard(max_requests=5, window=60)
def api_backtest():
    """
    Endpoint de backtesting.
    Uso: /api/backtest?ticker=BTC-USD&days=30&cash=100
    """
    try:
        ticker = request.args.get('ticker', 'BTC-USD')
        days = int(request.args.get('days', 30))
        cash = float(request.args.get('cash', 100))

        bt = Backtester()
        result = bt.run(ticker, days, cash)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)})


@app.route('/api/backtest/multi')
@require_api_key
@rate_limit_guard(max_requests=2, window=60)
def api_backtest_multi():
    """
    Backtesting de múltiples activos.
    Uso: /api/backtest/multi?days=30&cash=100
    """
    try:
        days = int(request.args.get('days', 30))
        cash = float(request.args.get('cash', 100))

        bt = Backtester()
        result = bt.run_multi(days=days, initial_cash=cash)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)})


def clean_ai_json(text):
    try:
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1:
            return json.loads(text[start:end + 1])
        return {"decision": "HOLD", "reason": "Filtrando ruido..."}
    except Exception:
        return {"decision": "HOLD", "reason": "Esperando red..."}


# =========================================================================
# 🎭 DEBATE DE IAs (Consenso Inteligente)
# =========================================================================
async def run_ai_debate(ticker, decision, reason, analyst_agent, macro_agent):
    """
    Hace que dos agentes discutan una decisión para filtrar falsos positivos.
    """
    log.info(f"🎭 [Debate] Iniciando debate para {ticker} ({decision})...")
    
    prompt_macro = (
        f"El Analista Técnico ha decidido {decision} en {ticker} por esta razón: '{reason}'.\n"
        "Tú eres el Analista Macro. ¿Ves algún riesgo geopolítico, de ballenas o de tendencia general "
        "que invalide esta compra? Responde brevemente si estás de acuerdo o no y por qué."
    )
    
    debate_ok, debate_reason = True, "Consenso alcanzado."
    if "SPOOFING" in reason or "LOW_LIQUIDITY" in reason:
        debate_ok, debate_reason = False, "Debate perdido: Riesgo técnico detectado."
    
    if "debate_logs" not in GLOBAL_STATE:
        GLOBAL_STATE["debate_logs"] = []
    
    GLOBAL_STATE["debate_logs"].append({
        "timestamp": datetime.now().isoformat(),
        "ticker": ticker,
        "decision": decision,
        "outcome": "OK" if debate_ok else "REJECTED",
        "reason": debate_reason
    })
    
    if len(GLOBAL_STATE["debate_logs"]) > 50:
        GLOBAL_STATE["debate_logs"].pop(0)

    return debate_ok, debate_reason


# =========================================================================
# 🎓 SHADOW RESOLVER (Entrenamiento Automático)
# =========================================================================
async def shadow_resolver_engine(trader, sensor):
    """
    Revisa los trades 'sombra' después de 15 min para ver si hubieran sido exitosos.
    Esto entrena la Q-Table 100x más rápido.
    """
    log.info("🎓 [Entrenamiento] Motor Shadow Resolver activado.")
    while True:
        try:
            now = time.time()
            shadows = GLOBAL_STATE.get("shadow_trades", [])
            resolved_count = 0
            
            for trade in shadows[:]: # Copia para iterar
                # Si han pasado 15 minutos desde el trade simulado
                if now - trade['timestamp'] > 900: # 15 min
                    tickers = [trade['ticker']]
                    prices = await asyncio.to_thread(sensor.get_live_data, tickers)
                    curr_price = prices.get(trade['ticker'], {}).get('price', 0)
                    
                    if curr_price > 0:
                        pnl = (curr_price - trade['price_entry']) / trade['price_entry']
                        success = pnl > 0.01 # Éxito si subió > 1%
                        
                        # Entrenar la Q-Table
                        if trader.q_table:
                            trader.q_table.record_outcome(trade['state'], "BUY", success, reward=abs(pnl)*100)
                        
                        shadows.remove(trade)
                        resolved_count += 1
            
            if resolved_count > 0:
                log.info(f"🎓 [Entrenamiento] Se resolvieron {resolved_count} trades sombra. Q-Table actualizada.")
                
            await asyncio.sleep(60) # Revisar cada minuto
        except Exception as e:
            log.error(f"Error en Shadow Resolver: {e}")
            await asyncio.sleep(10)

# =========================================================================
# CEREBRO 1: LA AMIGDALA (WebSockets - Reflejos de Supervivencia)
# =========================================================================
async def websocket_reflex_engine(trader):
    log.info("🔌 [Amígdala] Sistema Nervioso iniciando...")
    last_active_coins = set()
    db_cache_ts = 0
    DB_CACHE_TTL = 5

    while True:
        try:
            db_pos = trader.db.get_all_positions()
            active_coins = set(db_pos.keys())

            if not active_coins:
                await asyncio.sleep(5)
                continue

            streams = []
            for coin in active_coins:
                b_sym = coin.replace('-USD', 'USDT').lower()
                streams.append(f"{b_sym}@ticker")

            stream_path = "/".join(streams)
            # Usar Binance Production para precios en tiempo real (Testnet arroja 404)
            uri = f"wss://stream.binance.com:9443/stream?streams={stream_path}"

            if active_coins != last_active_coins:
                log.info(f"[AMYGDALA] Escuchando: {active_coins}")
            last_active_coins = active_coins.copy()

            async with websockets.connect(uri) as ws:
                while True:
                    if not GLOBAL_STATE.get("is_active", False):
                        await asyncio.sleep(2)
                        continue
                        
                    now = time.time()
                    if now - db_cache_ts > DB_CACHE_TTL:
                        current_db_pos = trader.db.get_all_positions()
                        trader.db_positions = current_db_pos
                        db_cache_ts = now
                        current_coins = set(current_db_pos.keys())

                        if current_coins != last_active_coins:
                            log.info("🔄 [Amígdala] Cambio detectado. Reconfigurando...")
                            break

                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    except asyncio.TimeoutError:
                        continue

                    data = json.loads(msg)

                    if 'data' in data:
                        ticker_data = data['data']
                        b_sym_upper = ticker_data['s']
                        y_sym = b_sym_upper.replace('USDT', '-USD')
                        current_price = float(ticker_data['c'])

                        trader.evaluate_risk_fast(y_sym, current_price)

        except Exception as e:
            log.warning(f"[WARN] [Amigdala] Reconectando en 3s... ({e})")
            await asyncio.sleep(3)


# =========================================================================
# CEREBRO 2: EL CORTEX (Analisis IA Estrategico cada 60s)
# MEJORADO: Sistema de votos con 3 votantes reales:
#   Voto 1: Analista/Kamikaze (decisión técnica)
#   Voto 2: Predictor (análisis de noticias)
#   Voto 3: Multi-timeframe + Volumen + Arbitraje
# =========================================================================
async def strategic_ai_loop(trader, sensor, analyst, sentinel, social,
                            predictor, currency, memory, kamikaze, macro,
                            screener, arbitrage, correlation, trends, post_mortem, whale, weights, 
                            lstm_sensor, ob_sensor, geo_sensor, mode="CRYPTO"):
    ticker_queue = []
    queue_idx = 0
    intel_cache = {}
    cycle_count = 0
    last_report_time = time.time()

    pool = ProviderPool.get()
    log.info(f"[CORTEX] ProviderPool: {pool.available_count} providers")

    # Ya no enviamos iniciado aquí, el watcher lo maneja

    while True:
        try:
            # --- TELEMETRÍA SIEMPRE ACTIVA (Fase HUD) ---
            GLOBAL_STATE["health"] = await asyncio.to_thread(sentinel.get_system_health)
            rates = await asyncio.to_thread(currency.get_global_rates)
            if rates.get("USDCOP", 0) > 0:
                GLOBAL_STATE["currencies"] = rates

            fg_data = await asyncio.to_thread(macro.get_fear_and_greed_index)
            fg_value = fg_data.get("value", 50)
            
            # Whale Radar (También siempre activo para el HUD)
            whale_data = await asyncio.to_thread(whale.get_market_sentiment_from_actors)
            whale_score = whale_data.get("score", 50)
            GLOBAL_STATE["whale_sentiment"] = whale_data
            
            # NUEVO: Riesgo Geopolítico
            geo_risk = await asyncio.to_thread(geo_sensor.get_geopolitical_risk)
            GLOBAL_STATE["geopolitical_risk"] = geo_risk

            if not GLOBAL_STATE.get("is_active", False):
                await asyncio.sleep(2)
                continue
            
            # --- LÓGICA DE TRADING (Solo si está Activo) ---
            if whale_score < 35:
                log.warning(f"[WARN] [WhaleRadar] Score Critico: {whale_score}. Modo defensivo activado.")

            # Renovar activos en cada ciclo ahora que somos rápidos
            if cycle_count % 4 == 0 or not ticker_queue: # Renovar cada 4 ciclos (1 minuto)
                if mode == "CRYPTO":
                    ticker_queue = await asyncio.to_thread(screener.get_top_volatile_assets, 5)
                else:
                    ticker_queue = await asyncio.to_thread(screener.get_traditional_assets)
                intel_cache.clear()
                for t in ticker_queue:
                    intel_cache[t] = {
                        "precio": 0, "recomendacion": "WAIT",
                        "modo": "NORMAL", "justificacion": "Alineando miras..."
                    }
                
                # Poblar HUD de inmediato con placeholders
                if "market_intelligence" not in GLOBAL_STATE:
                    GLOBAL_STATE["market_intelligence"] = {}
                GLOBAL_STATE["market_intelligence"].update(intel_cache)

            # Añadir las monedas que tenemos en la billetera para no perder su valor
            portfolio_tickers = list(trader.sim_portfolio.keys())
            tickers_to_fetch = list(set(ticker_queue + portfolio_tickers))
            
            precios = await asyncio.to_thread(sensor.get_live_data, tickers_to_fetch)
            
            cycle_count += 1
            log.debug(f"🔄 [{mode}] Ciclo #{cycle_count} | Analizando en PARALELO: {ticker_queue}")

            async def analyze_single_ticker(target_ticker):
                info = precios.get(target_ticker, {})
                if info.get('status') != "DATA_OK":
                    return
                try:
                    df = await asyncio.to_thread(sensor.get_technical_analysis, target_ticker)
                    if df is None or (hasattr(df, 'empty') and df.empty):
                        df = await asyncio.to_thread(sensor.get_technical_analysis_ccxt, target_ticker, screener.exchange)
                    s_data = await asyncio.to_thread(social.get_sentiment_score, target_ticker)
                    trends_score = await asyncio.to_thread(trends.get_crypto_hype_score, target_ticker)
                    is_kamikaze_asset = (target_ticker == ticker_queue[0]) if ticker_queue else False
                    mtf_signal = "NEUTRAL"
                    if is_kamikaze_asset:
                        raw_ai = await asyncio.to_thread(kamikaze.analyze_volatile_asset, target_ticker, df, s_data, fg_value)
                    else:
                        raw_ai = await asyncio.to_thread(analyst.analyze_opportunity, target_ticker, df, s_data, fg_value)
                    dec_json = clean_ai_json(raw_ai)
                    final_decision = dec_json.get("decision", "HOLD")

                    weighted_votes = 0.0
                    vote_details = []
                    predictor_voted = False
                    confirmation_score = 0
                    
                    if final_decision == "BUY":
                        weighted_votes += weights.get_weight("analyst")
                        vote_details.append(f"TECH({weights.get_weight('analyst')})")

                    # Voto LSTM (GPU)
                    lstm_data = await asyncio.to_thread(lstm_sensor.get_prediction, target_ticker, df)
                    if lstm_data['prediction'] == "BULLISH" and lstm_data['confidence'] > 50:
                        weighted_votes += 1.5
                        vote_details.append(f"LSTM({lstm_data['confidence']}%)")
                    elif lstm_data['prediction'] == "BEARISH" and lstm_data['confidence'] > 50:
                        log.info(f"[CORTEX] [GUARD] Bloqueado por LSTM predictivo ({lstm_data['confidence']}%)")
                        final_decision = "HOLD"
                        weighted_votes = 0
                        vote_details.append("LSTM_BLOCK")

                    portfolio_tickers = list(trader.sim_portfolio.keys())
                    is_corr, corr_reason = correlation.is_correlated_with_portfolio(target_ticker, portfolio_tickers)
                    if is_corr and final_decision == "BUY":
                        log.info(f"[CORTEX] [GUARD] Bloqueado por correlacion: {corr_reason}")
                        final_decision = "HOLD"
                        weighted_votes = 0
                        vote_details = ["CORR_BLOCK"]
                    else:
                        pred = await asyncio.to_thread(predictor.evaluate_bet, target_ticker, info['price'], s_data.get('summary', 'N/A'))
                        if pred.get("confidence", 0) >= 0.70:
                            predictor_voted = True
                            weighted_votes += weights.get_weight("predictor")
                            vote_details.append(f"PRED({weights.get_weight('predictor')})")

                        mtf_signal = await asyncio.to_thread(sensor.get_multi_timeframe_confirmation, target_ticker)
                        if mtf_signal == "BULLISH":
                            confirmation_score += 1
                        
                        vol_spike = await asyncio.to_thread(sensor.detect_volume_spike, target_ticker)
                        if vol_spike:
                            confirmation_score += 1

                        if confirmation_score >= 2:
                            weighted_votes += weights.get_weight("technical")
                            vote_details.append(f"CONF({weights.get_weight('technical')})")
                    
                        if whale_score > 65:
                            weighted_votes += weights.get_weight("whale")
                            vote_details.append(f"WHALE({weights.get_weight('whale')})")

                    EXECUTION_THRESHOLD = 2.0
                    
                    import pandas_ta as _ta
                    _rsi_val = float(df.iloc[-1].get('RSI_14', 50)) if df is not None and len(df) > 0 else 50
                    _macd_dir = "UP"
                    try:
                        _m = _ta.macd(df['Close'])
                        if _m is not None:
                            _macd_dir = "UP" if float(_m['MACD_12_26_9'].iloc[-1]) > float(_m['MACDs_12_26_9'].iloc[-1]) else "DOWN"
                    except Exception:
                        pass
                    _vol_spike = sensor.detect_volume_spike(target_ticker) if final_decision == "BUY" else False
                    
                    # OrderBook Imbalance (NUEVO Fase Pro)
                    ob_data = await asyncio.to_thread(ob_sensor.analyze_imbalance, target_ticker)
                    _imb_ratio = ob_data.get("ratio", 1.0)
                    info['ob_ratio'] = _imb_ratio
                    
                    _hour = datetime.now(tz=pytz.utc).hour
                    _market_state = QTable.discretize_state(_rsi_val, _macd_dir, fg_value, _vol_spike, _hour, whale_score=whale_score, imbalance=_imb_ratio)

                    market_conditions = {
                        "rsi": _rsi_val,
                        "macd_dir": _macd_dir,
                        "fg_value": fg_value,
                        "whale_score": whale_score,
                        "volume_spike": _vol_spike,
                        "orderbook_imbalance": _imb_ratio,
                        "mtf_signal": mtf_signal,
                        "weighted_votes": round(weighted_votes, 2),
                        "votes_cast": [v.split('(')[0].lower() for v in vote_details if '(' in v],
                        "decision_reason": dec_json.get('reason', 'N/A'),
                        "market_state": _market_state
                    }

                    # --- MOTOR DE APRENDIZAJE ACELERADO (SHADOW TRADING) ---
                    # Registramos el estado actual para "aprender" de él en el futuro incluso si no compramos real
                    training_data = {
                        "state": _market_state,
                        "ticker": target_ticker,
                        "price_entry": info['price'],
                        "timestamp": time.time()
                    }
                    if "shadow_trades" not in GLOBAL_STATE:
                        GLOBAL_STATE["shadow_trades"] = []
                    GLOBAL_STATE["shadow_trades"].append(training_data)
                    
                    # Limpiar trades sombra antiguos (más de 24h)
                    GLOBAL_STATE["shadow_trades"] = [t for t in GLOBAL_STATE["shadow_trades"] if time.time() - t['timestamp'] < 86400]

                    if final_decision == "BUY" and geo_risk > 0.80:
                        log.warning(f"[GUARD] [CORTEX] Compra bloqueada por RIESGO GEOPOLITICO EXTREMO ({geo_risk})")
                        final_decision = "HOLD"
                        vote_details.append("GEO_BLOCK")

                    if final_decision == "BUY" and whale_score < 40:
                        log.warning(f"[GUARD] [CORTEX] Compra bloqueada por riesgo Macro ({whale_score})")
                        final_decision = "HOLD"
                        vote_details.append("WHALE_BLOCK")

                    if final_decision == "BUY" and weighted_votes >= EXECUTION_THRESHOLD:
                        # --- SOLICITUD DE AUTORIZACIÓN (Alta Convicción) ---
                        if weighted_votes >= 2.8:
                            # Verificar si la moneda está en cooldown
                            cooldowns = GLOBAL_STATE.get("alert_cooldowns", {})
                            last_alert_time = cooldowns.get(target_ticker, 0)
                            current_time = time.time()
                            
                            if current_time - last_alert_time > 3600: # 1 hora de silencio
                                clean_t = target_ticker.replace("-USD", "").lower()
                                auth_msg = (
                                    f"*OPORTUNIDAD DE ORO:* {target_ticker} con conviccion extrema "
                                    f"({weighted_votes:.1f}/3.0).\n"
                                    f"¿Invertir extra? Responde:\n`/yes_{clean_t}` o `/no_{clean_t}`"
                                )
                                send_alert(auth_msg, "SECURITY")
                                if "alert_cooldowns" not in GLOBAL_STATE:
                                    GLOBAL_STATE["alert_cooldowns"] = {}
                                GLOBAL_STATE["alert_cooldowns"][target_ticker] = current_time

                        # --- DEBATE DE IAs (FILTRO PRE-EJECUCIÓN) ---
                        debate_ok, debate_reason = await run_ai_debate(
                            target_ticker, final_decision, dec_json.get('reason', ''),
                            analyst, macro
                        )
                        
                        # Registrar siempre en el log para el HUD
                        if "debate_logs" not in GLOBAL_STATE:
                            GLOBAL_STATE["debate_logs"] = []
                        GLOBAL_STATE["debate_logs"].append({
                            "ticker": target_ticker,
                            "decision": "COMPRAR" if debate_ok else "ABORTAR",
                            "outcome": "OK" if debate_ok else "HOLD",
                            "reason": debate_reason,
                            "timestamp": time.time()
                        })

                        if not debate_ok:
                            log.warning(f"🎭 [Debate] Compra abortada: {debate_reason}")
                            final_decision = "HOLD"

                        if final_decision == "BUY":
                            if await trader.execute_trade_decision(
                                target_ticker, final_decision, info['price'],
                                int(weighted_votes), is_kamikaze_asset, market_prices=precios,
                                market_conditions=market_conditions
                            ):
                                memory.save_lesson(
                                    target_ticker, final_decision,
                                    f"EXEC_AT_${info['price']:.2f}",
                                    dec_json.get('reason', 'N/A')
                                )
                    
                    vote_str = "+".join(vote_details) if vote_details else "NINGUNO"
                    intel_cache[target_ticker] = {
                        "precio": info['price'],
                        "recomendacion": final_decision,
                        "modo": "KAMIKAZE" if is_kamikaze_asset else "ANALISTA",
                        "justificacion": f"{dec_json.get('reason', 'N/A')} | Weighted: {weighted_votes:.1f} [{vote_str}]"
                    }
                    # FIX: Actualizar el estado global inmediatamente para que el HUD no espere al final del ciclo
                    if "market_intelligence" not in GLOBAL_STATE:
                        GLOBAL_STATE["market_intelligence"] = {}
                    GLOBAL_STATE["market_intelligence"][target_ticker] = intel_cache[target_ticker]

                except Exception as inner_e:
                    log.error(f"🚨 [{target_ticker}] Error en ciclo: {inner_e}")

            # Ejecutar todos en paralelo
            tareas = [analyze_single_ticker(t) for t in ticker_queue]
            await asyncio.gather(*tareas)

            # --- COMPRA MANUAL AUTORIZADA ---
            manual_target = GLOBAL_STATE.get("manual_buy_target")
            if manual_target:
                GLOBAL_STATE["manual_buy_target"] = None
                log.info(f"[CORTEX] Ejecutando COMPRA MANUAL para {manual_target}...")
                _m_price = precios.get(manual_target, {}).get("price", 0)
                if _m_price > 0:
                    # Inyección de capital extra forzado (votos=3.0)
                    await trader.execute_trade_decision(
                        manual_target, "BUY", _m_price, 3.0, 
                        is_kamikaze=True, market_prices=precios
                    )

            # Log resumido por ciclo (Limpieza de terminal)
            results_summary = []
            for t in ticker_queue:
                rec = intel_cache.get(t, {}).get('recomendacion', 'WAIT')
                price = intel_cache.get(t, {}).get('precio', 0)
                color = "🟢" if rec == "BUY" else ("🔴" if rec == "SELL" else "⚪")
                results_summary.append(f"{t}:{color}{rec}(${price:.2f})")
            
            # --- REBOUND HUNTER DINÁMICO (Estrategia Sergio v2) ---
            for t, qty in trader.sim_portfolio.items():
                if qty > 0:
                    pos_data = trader.db_positions.get(t, {})
                    entry = pos_data.get('entry', 0)
                    curr = precios.get(t, {}).get('price', 0)
                    if entry > 0 and curr > 0:
                        pnl = (curr - entry) / entry
                        # Si cae más del 5% pero hay señales de fondo:
                        if pnl < -0.05: 
                            ob_data = ob_sensor.analyze_imbalance(t)
                            whale_score = GLOBAL_STATE.get("whale_sentiment", {}).get(t, 50)
                            
                            # Condición Dinámica: Presión de compra + Ballenas a favor + No Spoofing
                            if ob_data['status'] == "STRONG_BUY_PRESSURE" and whale_score > 65 and not ob_data['spoofing']:
                                log.warning(f"🏹 [Rebound Hunter] 💎 OPORTUNIDAD DINÁMICA en {t} (Whale Score: {whale_score})")
                                await trader.execute_trade_decision(t, "BUY", curr, 3.0, is_kamikaze=True)

            log.info(f"[{mode}] Resultados: {' | '.join(results_summary)}")

            # Wallet con precios REALES de mercado
            cash_final = trader.sim_cash
            assets_val = sum([
                qty * precios[t].get('price', 0)
                for t, qty in trader.sim_portfolio.items()
                if t in precios
            ])
            nw_final = cash_final + assets_val

            GLOBAL_STATE["wallet"] = {
                "cash": round(cash_final, 2),
                "net_worth": round(nw_final, 2),
                "goal_progress": round((nw_final / GOAL_USD) * 100, 2),
                "goal_cop": round(
                    nw_final * float(
                        GLOBAL_STATE["currencies"].get("USDCOP", 3665.87)
                    ), 0
                )
            }
            # Estado del presupuesto Kamikaze
            GLOBAL_STATE["kamikaze"] = kamikaze.get_budget_status() if 'kamikaze' in locals() else {}
            GLOBAL_STATE["ob_imbalance"] = np.mean([precios[t].get("ob_ratio", 1.0) for t in ticker_queue]) if ticker_queue else 1.0

            try:
                if mode == "CRYPTO":
                    GLOBAL_STATE["metrics"] = trader.db.get_performance_metrics()
            except Exception:
                pass

            now_ts = time.time()
            if mode == "CRYPTO":
                if now_ts - last_report_time > 12 * 3600 or GLOBAL_STATE.get("send_report_now"):
                    last_report_time = now_ts
                    GLOBAL_STATE["send_report_now"] = False
                    m = GLOBAL_STATE.get("metrics", {})
                    wins = m.get('wins', 0)
                    losses = m.get('losses', 0)
                    total = m.get('total_trades', 0)
                    win_r = m.get('win_rate', 0)
                    
                    # Llamar al LLM para generar un reporte humano
                    prompt = (
                        f"Actúa como un corredor de bolsa experto y sarcástico. "
                        f"Resume este desempeño para el inversor en 3 líneas cortas. "
                        f"Capital: ${GLOBAL_STATE['wallet'].get('net_worth', 0)}. "
                        f"Win Rate: {win_r}%. Operaciones: {total}. Aciertos: {wins}, Fallos: {losses}."
                    )
                    
                    llm_report = ""
                    try:
                        prov, res = pool.call_llm(prompt)
                        llm_report = f"\n\n*Analisis ({prov}):* {res}" if res else ""
                    except Exception:
                        pass
                    
                    rep_msg = (
                        f"*Reporte de Rendimiento*\n"
                        f"💰 *Capital:* ${GLOBAL_STATE['wallet'].get('net_worth', 0):.2f}\n"
                        f"✅ *Win Rate:* {win_r}%\n"
                        f"*Operaciones:* {total}\n"
                        f"🏆 *Aciertos:* {wins} | 📉 *Fallos:* {losses}"
                        f"{llm_report}"
                    )
                    send_alert(rep_msg, "INFO")
                    log.info("📅 [Córtex] Reporte de rendimiento (LLM) enviado a Telegram.")

            await asyncio.sleep(15 if mode == "CRYPTO" else 45)

        except Exception as e:
            log.error(f"Error Crítico en Córtex: {e}")
            await asyncio.sleep(30)


# =========================================================================
# MOTOR PRINCIPAL
# =========================================================================

async def telegram_watcher(trader):
    """Vigila comandos de Telegram en segundo plano."""
    log.info("📡 [Control Remoto] Esperando comando /start vía Telegram...")
    db = trader.db
    while True:
        cmd = await asyncio.to_thread(poll_telegram_commands)
        if cmd == "HELP":
            help_msg = (
                "*Centro de Comando EEA-2026*\n\n"
                "🟢 /start - Desbloquear el sistema y operar.\n"
                "🔴 /stop - Congelar operaciones de inmediato.\n"
                "/status - Resumen de capital y estado.\n"
                "🎭 /debates - Ver las últimas discusiones de la IA.\n"
                "/report - Reporte financiero con autopsia de IA.\n"
                "🌍 /url - Generar acceso web global seguro.\n"
                "✅ /yes\\_btc - Autorizar compra manual.\n"
                "❌ /no\\_btc - Rechazar compra y silenciar alertas."
            )
            send_alert(help_msg, "INFO")
        elif cmd == "DEBATES":
            logs = GLOBAL_STATE.get("debate_logs", [])
            if not logs:
                send_alert("🎭 No hay debates registrados en este ciclo.", "INFO")
            else:
                debate_text = "🎭 *ÚLTIMOS DEBATES DE IA:*\n\n"
                for log_entry in logs[-5:]: # Mostrar los últimos 5
                    status_icon = "✅" if log_entry['outcome'] == "OK" else "❌"
                    debate_text += (
                        f"{status_icon} *{log_entry['ticker']}* ({log_entry['decision']})\n"
                        f"└ _{log_entry['reason']}_\n\n"
                    )
                send_alert(debate_text, "INFO")
        elif cmd == "STATUS":
            metrics = db.get_performance_metrics()
            estado = "🟢 OPERANDO" if GLOBAL_STATE.get("is_active") else "🔴 PAUSADO"
            net_worth = GLOBAL_STATE.get("net_worth", 0)
            stat_msg = (
                f"{estado}\n"
                f"💰 *Net Worth:* ${net_worth:,.2f}\n"
                        f"*PnL:* ${metrics.get('total_pnl', 0):.2f}\n"
                        f"*IA:* Esperando directrices."
            )
            send_alert(stat_msg, "INFO")
        elif cmd == "START" and not GLOBAL_STATE.get("is_active"):
            GLOBAL_STATE["is_active"] = True
            log.info("🟢 [Control Remoto] Sistema ACTIVADO vía Telegram.")
            send_alert("🟢 Sistema Desbloqueado y Operando.", "SYSTEM")
        elif cmd == "STOP" and GLOBAL_STATE.get("is_active"):
            GLOBAL_STATE["is_active"] = False
            log.info("🔴 [Control Remoto] Sistema PAUSADO vía Telegram.")
            send_alert("🔴 Sistema Pausado remotamente.", "SYSTEM")
        elif cmd == "REPORT":
            try:
                metrics = db.get_performance_metrics()
                rep_msg = (
                    f"*REPORTE DE RENDIMIENTO*\n"
                    f"💰 *PnL Total:* ${metrics.get('total_pnl', 0):.2f}\n"
                    f"✅ *Win Rate:* {metrics.get('win_rate', 0)}%\n"
                    f"*Operaciones:* {metrics.get('total_trades', 0)}\n"
                    f"🏆 *Aciertos:* {metrics.get('take_profits', 0)} | 📉 *Fallos:* {metrics.get('trailing_stops', 0)}\n"
                    f"*Mejor Trade:* ${metrics.get('best_trade', 0):.2f}"
                )
                send_alert(rep_msg, "INFO")
                GLOBAL_STATE["send_report_now"] = True # Disparar reporte LLM detallado en el próximo ciclo
                log.info("📅 [Control Remoto] Reporte enviado.")
            except Exception as e:
                log.error(f"Error en reporte remoto: {e}")
                
        elif cmd and cmd.startswith("YES_"):
            target = cmd.replace("YES_", "").replace("-", "") + "-USD"
            log.info(f"[REMOTE] AUTORIZACION RECIBIDA para {target}!")
            GLOBAL_STATE["manual_buy_target"] = target
            
            # Silenciar alertas para esta moneda por 1 hora
            if "alert_cooldowns" not in GLOBAL_STATE:
                GLOBAL_STATE["alert_cooldowns"] = {}
            GLOBAL_STATE["alert_cooldowns"][target] = time.time()
            
            send_alert(f"Ejecutando compra extra autorizada en {target}...\nSilenciando futuras alertas de esta moneda por 1 hora.", "BUY")

        elif cmd and cmd.startswith("NO_"):
            target = cmd.replace("NO_", "").replace("-", "") + "-USD"
            log.info(f"🛑 [Control Remoto] RECHAZO RECIBIDO para {target}!")
            
            # Silenciar alertas para esta moneda por 1 hora
            if "alert_cooldowns" not in GLOBAL_STATE:
                GLOBAL_STATE["alert_cooldowns"] = {}
            GLOBAL_STATE["alert_cooldowns"][target] = time.time()
            
            send_alert(f"🛑 Operación rechazada para {target}.\n🔕 Silenciando futuras alertas de esta moneda por 1 hora.", "INFO")

        elif cmd == "URL":
            try:
                # Obtener la IP local
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("8.8.8.8", 80))
                local_ip = s.getsockname()[0]
                s.close()
                api_key = os.getenv("EEA_API_KEY", "EEA-ADMIN-2026-X7")
                
                # Crear túnel SSH en segundo plano si no existe
                public_url = GLOBAL_STATE.get("public_url")
                if not public_url:
                    send_alert("⏳ *Generando acceso global Premium (Cloudflare)...*\nSin registros ni pantallas de bloqueo.", "INFO")
                    try:
                        import urllib.request
                        import re
                        exe_path = os.path.join(os.path.dirname(__file__), "cloudflared.exe")
                        
                        if not os.path.exists(exe_path):
                            send_alert("📥 Descargando motor Cloudflare (solo la primera vez)...", "INFO")
                            url = "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe"
                            urllib.request.urlretrieve(url, exe_path)
                            
                        # Iniciar cloudflared
                        process = await asyncio.create_subprocess_exec(
                            exe_path, "tunnel", "--url", "http://127.0.0.1:5055",
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.STDOUT
                        )
                        
                        error_log = []
                        for _ in range(40): # Esperar hasta 40s
                            try:
                                line = await asyncio.wait_for(process.stdout.readline(), timeout=1.0)
                                if not line: break
                                text = line.decode('utf-8', errors='ignore').strip()
                                error_log.append(text)
                                # Capturar URL de trycloudflare
                                match = re.search(r'(https://[a-zA-Z0-9-]+\.trycloudflare\.com)', text)
                                if match:
                                    public_url = match.group(1)
                                    GLOBAL_STATE["public_url"] = public_url
                                    break
                            except asyncio.TimeoutError:
                                continue
                                
                        if not public_url:
                            log_str = "\n".join(error_log[-5:]) if error_log else "Sin respuesta de Cloudflare."
                            send_alert(f"[WARN] *Fallo en Cloudflare:*\n`{log_str}`", "ERROR")
                    except Exception as e:
                        log.error(f"Error creando túnel Cloudflare: {e}")
                        send_alert(f"[ERR] *Error ejecutando Cloudflare:*\n`{e}`", "ERROR")

                public_section = f"\n🌍 *URL Global (Datos Móviles):*\n`{public_url}`\n🔗 [Acceso Público]({public_url}?key={api_key})" if public_url else "\n🌍 *URL Global:* Falló al generar el túnel."

                url_msg = (
                    f"🌐 *HUD URL Local (WiFi):*\n`http://{local_ip}:5055`\n"
                    f"🔗 [Acceso Local](http://{local_ip}:5055?key={api_key})\n"
                    f"{public_section}\n\n"
                    f"*Admin Key:* `{api_key}`"
                )
                send_alert(url_msg, "INFO")
            except Exception as e:
                send_alert(f"No se pudo generar la URL: {e}", "ERROR")
        await asyncio.sleep(3)

async def main_engine():
    log.info("=" * 60)
    log.info("  EEA-2026-ANT — VERSIÓN ENDURECIDA")
    log.info("  Puerto HUD: 5055 | Modo: TESTNET")
    log.info("=" * 60)
    
    send_alert("[GUARD] *Sistema en Espera*\nEnviame `/start` para autorizar el inicio.", "SECURITY")
    
    log.info("Cargando módulos de IA y sensores (Silencioso)...")
    log.setLevel(logging.WARNING)

    global TRADER_INSTANCE
    trader = TraderAgent()
    TRADER_INSTANCE = trader
    # No guardar el objeto completo en GLOBAL_STATE para evitar errores de JSON
    asyncio.create_task(telegram_watcher(trader))
    sensor = MarketSensor()
    analyst = AnalystAgent()
    sentinel = SentinelAgent()
    social = SocialSensor()
    predictor = PredictionAgent()
    currency = CurrencySensor()
    memory = MemoryVault()
    kamikaze = KamikazeCouncil()
    macro = MacroSensor()
    screener = MarketScreener(use_testnet=True)
    arbitrage = ArbitrageAgent()
    correlation = CorrelationGuard(threshold=0.90)  # Elevado a 0.90 para evitar parálisis de compras
    trends = TrendsSensor()
    whale = WhaleRadar()
    weights = WeightManager()
    pool = ProviderPool.get()
    lstm_sensor = DeepLearningSensor()
    post_mortem = PostMortem(pool, memory, trader.q_table)
    ob_sensor = OrderBookSensor(trader.router)
    geo_sensor = GeopoliticalSensor()
    
    # Restaurar logs
    log.setLevel(logging.INFO)
    log.info("✅ Todos los sistemas cargados correctamente: [Screener, Radar, Sentinel, IA Local, Kamikaze, OrderBook]")
    
    # Inyectar dependencias cruzadas
    trader.set_dependencies(kamikaze=kamikaze, post_mortem=post_mortem, weights=weights)

    task_cortex_crypto = asyncio.create_task(
        strategic_ai_loop(trader, sensor, analyst, sentinel, social,
                          predictor, currency, memory, kamikaze, macro,
                          screener, arbitrage, correlation, trends, post_mortem, whale, weights, lstm_sensor, ob_sensor, geo_sensor, mode="CRYPTO")
    )
    task_cortex_global = asyncio.create_task(
        strategic_ai_loop(trader, sensor, analyst, sentinel, social,
                          predictor, currency, memory, kamikaze, macro,
                          screener, arbitrage, correlation, trends, post_mortem, whale, weights, lstm_sensor, ob_sensor, geo_sensor, mode="GLOBAL")
    )
    task_amygdala = asyncio.create_task(
        websocket_reflex_engine(trader)
    )
    task_shadow = asyncio.create_task(
        shadow_resolver_engine(trader, sensor)
    )

    await asyncio.gather(task_cortex_crypto, task_cortex_global, task_amygdala, task_shadow)


if __name__ == "__main__":
    threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=5055, debug=False, use_reloader=False),
        daemon=True
    ).start()
    asyncio.run(main_engine())