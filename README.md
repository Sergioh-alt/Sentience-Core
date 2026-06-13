# EEA-2026-ANT — Autonomous Trading Exoskeleton

[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python)](https://python.org)
[![Binance API](https://img.shields.io/badge/Binance-API-F0B90B?logo=binance)](https://binance.com)
[![License](https://img.shields.io/badge/License-MIT-blue)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production-brightgreen)]()
[![Agents](https://img.shields.io/badge/Agent%20Count-8-FF6F00)]()

Multi-agent AI system that autonomously trades cryptocurrency on Binance to bootstrap its own hardware evolution. Built with a constitutional swarm architecture, local LLM inference, and real-time market analysis.

## Technical Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        EEA-2026-ANT                              │
│                                                                  │
│  🧠 CORTEX (polling — 60s cycle)     ⚡ AMYGDALA (WebSocket)    │
│  ├── MarketSensor                     ├── Binance WS             │
│  ├── AnalystAgent (SOTA)              ├── TrailingStop           │
│  ├── Strategist Agent                 └── TakeProfit             │
│  ├── PredictionAgent                                            │
│  ├── SocialSensor (6 sources)         📊 HUD Dashboard           │
│  ├── MacroSensor                      ├── :5055/                 │
│  ├── MarketScreener                   ├── /api/metrics           │
│  └── CurrencySensor                   └── /api/data              │
│         │                                                       │
│         ▼                                                       │
│  ┌── TraderAgent ◄── Guardian (Constitutional)                  │
│  │    (Execute)     ├── Risk Manager                            │
│  │                  ├── Post-Mortem (Q-Learning)                │
│  │                  └── Sentinel (HW Monitor)                   │
│  └──────────┬──────────────────────────────────────────────────┘
│             ▼                                                    │
│    ProviderPool ◄── Multi-LLM (Ollama/Groq/Cerebras/DeepSeek)   │
│    ExchangeRouter ──► Binance API                               │
│    DatabaseManager ──► SQLite (eea_core.db)                     │
│    Alerts ──► Telegram (optional)                                │
└──────────────────────────────────────────────────────────────────┘
```

## Agent Swarm Overview

| Agent | Function | LLM |
|---|---|---|
| **MarketSensor** | Real-time prices (yfinance + AlphaVantage fallback) | No |
| **MarketScreener** | Binance volatility scanner | No |
| **AnalystAgent** | Technical signals (RSI, MACD, BB) + scoring | Yes |
| **Strategist** | Probabilistic scenarios, strategy generation | Yes |
| **SocialSensor** | News aggregation from 6 sources + sentiment | Yes |
| **MacroSensor** | Fear & Greed Index + CoinGecko volume | No |
| **CurrencySensor** | USD/COP, EUR/USD, DXY rates | No |
| **SentinelAgent** | CPU/RAM/GPU temperature monitoring | No |
| **Risk Manager** | Financial & technical risk assessment | Yes |
| **Guardian** | Constitutional consensus enforcement | Yes |
| **Post-Mortem** | Outcome analysis, Q-learning, genetic evolution | Yes |
| **TraderAgent** | Binance order execution | No |

### Key Mechanisms

- **Constitutional Consensus**: 8 agents debate trades through a Guardian-enforced weighted voting system with 90% consensus threshold
- **P-THERMAL**: Automatic trading pause when GPU exceeds 78°C
- **Safe Start**: 10 consecutive successful paper trades before production activation
- **Multi-LLM Provider Pool**: Circuit-breaker pattern across Ollama (local), Groq, Cerebras, DeepSeek, Gemini
- **Post-Mortem Learning**: Q-table updates, genetic algorithm evolution, and ChromaDB vectorized lessons after every cycle
- **Insight Incubator**: Side-channel opportunity detection (arbitrage, code improvements, news signals)

## Hardware Requirements

| Component | Minimum | Recommended |
|---|---|---|
| **CPU** | 4 cores / 8 threads | AMD Ryzen 7 5800X (8C/16T) |
| **GPU** | NVIDIA 8GB VRAM | RTX 3060 Ti (8GB) |
| **RAM** | 16 GB | 32 GB |
| **Storage** | 50 GB SSD | 100 GB SSD |
| **OS** | Windows 10 / Linux | Windows 11 / Ubuntu 22.04 |

### LLM Reasoning Modes

| Mode | Min VRAM | Models | Use Case |
|---|---|---|---|
| **Full Reasoning** | 24 GB | deepseek-r1:70b, llama2:70b | Maximum analysis quality |
| **Quantized Q4** | 12 GB | deepseek-r1:70b-q4, llama2:70b-q4 | Balance performance/VRAM |
| **Quantized Q3 (CPU)** | 0 GB | deepseek-r1:7b, mistral:7b | Low-resource environments |

## Performance Metrics

| Metric | Value |
|---|---|
| **Analysis cycle** | ~60 seconds |
| **Consensus rounds** | 3 max (emergency on round 3) |
| **Max single trade** | Configurable (default: $500 USD) |
| **Max drawdown** | 10% |
| **Hardware goal** | RTX 5090 ($2,000 USD target) |

## Installation

```bash
# Clone and enter directory
cd EEA_2026_ANT

# Install dependencies
pip install -r requirements.txt

# Install Ollama for local LLM inference
# https://ollama.com/
ollama run llama3.2

# Configure environment
cp .env.example .env
# Edit .env with your API keys (optional — prioritizes local Ollama)
```

## Configuration

`.env` file:

```ini
BINANCE_API_KEY=your_key
BINANCE_SECRET_KEY=your_secret
TELEGRAM_BOT_TOKEN=optional
TELEGRAM_CHAT_ID=optional
MAX_SPEND_USD=500
MAX_DRAWDOWN_PCT=10
SAFE_START_MODE=true
```

## Execution

```bash
python core/app_orchestrator.py
```

| Endpoint | Description |
|---|---|
| `http://localhost:5055` | HUD Dashboard |
| `http://localhost:5055/api/data` | Real-time market data |
| `http://localhost:5055/api/metrics` | System metrics |

## Safe Start Protocol

1. **Paper Trading**: First 10 successful rounds with >65% confidence
2. **Production**: Guardian automatically transitions after Safe Start completion
3. **Hardware Protection**: Sentinel monitors GPU temp, CPU load, RAM usage
4. **Emergency Stop**: Guardian can halt all trading via `panic_kill.sh`

## Development Status

EEA-2026 is a production-ready autonomous trading system. The architecture emphasizes safety (constitutional constraints, thermal monitoring, safe start) while pursuing its primary objective: bootstrapping hardware upgrades through market profits.

## Related

- [Shura](https://github.com/YOUR_USER/shura) — Financial analysis dashboard companion
