# AGENTS.md — Project Guidelines for AI Agents

## Project Overview

Real-time stock portfolio analysis backend. Clients connect via WebSockets, request analysis on tickers, and receive streaming metric results. Three concurrent writers (client requests, analysis completions, market updates) modify shared portfolio state in Redis.

## Tech Stack

- **Python 3.10+** / **FastAPI** / **asyncio**
- **Redis 8+** with **RedisJSON** module (ships by default in `redis:latest` Docker image)
- **Pydantic v2** for models and settings
- **WebSockets** for bidirectional client communication

## Architecture

See `documentation/adr/001-system-architecture.md` for full details.

Key patterns:
- **RedisJSON + Lua hybrid** — direct `JSON.SET`/`JSON.GET` for simple ops, Lua scripts calling JSON commands for atomic multi-step mutations
- **Cancel-on-switch** — new analysis request cancels in-flight tasks for previous ticker
- **Snapshot consistency** — all 5 metrics computed against the same portfolio state snapshot
- **Session TTL** — 24hr Redis key expiry, refreshed on activity

## Project Structure

```
app/
  main.py           - FastAPI app, WebSocket endpoint, lifespan
  models.py         - Pydantic models for messages and state
  redis_client.py   - Redis connection + RedisJSON + Lua scripts
  portfolio.py      - Portfolio state CRUD (thin layer over redis_client)
  analysis.py       - Parallel metric computation engine
  market.py         - Background market data updater
  config.py         - Pydantic Settings (env prefix: PORTFOLIO_)
scripts/
  demo_client.py    - WebSocket test/demo script
documentation/
  adr/              - Architecture Decision Records
```

## Running

```bash
# Redis (requires Redis 8+ with JSON module)
docker run -d --name redis -p 6379:6379 redis:latest

# Server
pip install -r requirements.txt
uvicorn app.main:app --reload

# Demo client
python scripts/demo_client.py
```

## Code Conventions

- Type hints everywhere (Python 3.10+ union syntax: `X | None`)
- Pydantic models for all serialization boundaries
- `async`/`await` throughout — no blocking calls
- Lua scripts are inline strings in `redis_client.py`, registered via `EVALSHA` at startup
- Configuration via environment variables with `PORTFOLIO_` prefix (see `app/config.py`)

## Important Constraints

- **Never decode full JSON in Lua when a path query suffices** — use `JSON.GET key $.path` instead of `cjson.decode(redis.call('GET', key))`
- **Never write to Redis without refreshing TTL** — every mutation must call `EXPIRE`
- **Analysis results must use the snapshot taken at analysis start** — do not re-read portfolio state mid-analysis
- **Cancelled tasks must exit cleanly** — catch `asyncio.CancelledError`, do not write partial results
- Portfolio state mutations go through `redis_client.py` Lua scripts — never write to Redis directly from application code
- The `portfolio.py` module is the public Python API for state operations — other modules should not import from `redis_client.py`
- Read `documentation/adr/001-system-architecture.md` before making architectural changes
- Test against a real Redis 8+ instance with the JSON module loaded
