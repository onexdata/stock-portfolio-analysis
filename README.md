# Real-Time Stock Portfolio Analysis Backend

A backend service that provides real-time stock portfolio analysis over WebSockets. Clients connect, request analysis on tickers in their portfolio, and receive streaming metric results as they compute in parallel.

## Architecture

Three concurrent operations modify shared portfolio state:

1. **Client requests** — set `current_analysis` when a user asks to analyze a ticker
2. **Analysis completions** — append metric results as each of the 5 parallel computations finishes
3. **Market updates** — recalculate `total_value` every 30 seconds from mock price data

State consistency is maintained through a **RedisJSON + Lua script hybrid**:
- Simple reads/writes use direct `JSON.SET`/`JSON.GET` commands
- Multi-step mutations use Lua scripts that call JSON path commands internally, executing atomically on the Redis server

See [`documentation/adr/001-system-architecture.md`](documentation/adr/001-system-architecture.md) for full architectural decisions and trade-offs.

## Key Design Decisions

| Decision | Rationale |
|---|---|
| **WebSockets** over SSE | Bidirectional — client sends requests and receives streaming results on the same connection |
| **RedisJSON + Lua** over plain strings | O(1) array appends via `JSON.ARRAPPEND`, path queries avoid decoding full documents |
| **Cancel-on-switch** | When user switches tickers, cancel in-flight analysis to prevent interleaved results |
| **Snapshot consistency** | All 5 metrics computed against the same portfolio snapshot for internal coherence |
| **Session TTL** | Redis native `EXPIRE` at 24 hours, refreshed on every interaction |

## Prerequisites

- **Python 3.10+**
- **Redis 8+** with the JSON module (ships by default in `redis:latest`)
- **Node.js 22+** (only if using the Chrome DevTools MCP server)

## Quick Start

### 1. Start Redis

```bash
docker run -d --name redis -p 6379:6379 redis:latest
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Start the Server

```bash
uvicorn app.main:app --reload
```

### 4. Run the Demo Client

```bash
python scripts/demo_client.py
```

The demo client connects to a WebSocket session, requests analysis on AAPL, then switches to GOOGL mid-analysis to demonstrate cancel-on-switch. You'll see streaming metric results printed as they arrive.

## Configuration

All settings are configurable via environment variables with the `PORTFOLIO_` prefix:

| Variable | Default | Description |
|---|---|---|
| `PORTFOLIO_REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `PORTFOLIO_SESSION_TTL_SECONDS` | `86400` | Session expiry (24 hours) |
| `PORTFOLIO_MARKET_UPDATE_INTERVAL_SECONDS` | `30.0` | Market update frequency |

## API

### WebSocket Endpoint

```
ws://localhost:8000/ws/{session_id}
```

**Send:**
```json
{"action": "analyze", "ticker": "AAPL"}
```

**Receive** (streamed as each metric completes):
```json
{
  "type": "analysis_result",
  "ticker": "AAPL",
  "metric": "portfolio_risk",
  "value": 0.23,
  "timestamp": "2026-02-26T10:30:00Z"
}
```

**Metrics computed:** `portfolio_risk`, `concentration`, `correlation`, `momentum`, `allocation_score`

### Health Check

```
GET http://localhost:8000/health
```

## Project Structure

```
app/
  main.py           - FastAPI app, WebSocket endpoint, lifespan
  models.py         - Pydantic models for messages and state
  redis_client.py   - Redis connection + RedisJSON + Lua scripts
  portfolio.py      - Portfolio state CRUD (Python API over redis_client)
  analysis.py       - Parallel metric computation engine
  market.py         - Background market data updater
  config.py         - Settings via pydantic-settings
scripts/
  demo_client.py    - WebSocket test/demo script
  setup_mcp.py      - Cross-platform Chrome DevTools MCP setup
documentation/
  adr/
    001-system-architecture.md
```
