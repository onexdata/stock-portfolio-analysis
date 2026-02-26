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
config.json           - Feature-structured behavioral config (see ADR-003)
app/
  main.py           - FastAPI app, WebSocket endpoint, POST /session, lifespan
  models.py         - Pydantic models for messages and state
  redis_client.py   - Redis connection + RedisJSON + Lua scripts
  portfolio.py      - Portfolio state CRUD (thin layer over redis_client)
  analysis.py       - Parallel metric computation engine
  market.py         - Background market data updater
  config.py         - Pydantic config hierarchy (config.json) + EnvSettings (env vars)
scripts/
  demo_client.py    - WebSocket test/demo script
documentation/
  adr/              - Architecture Decision Records
  diagrams/
    system-architecture.drawio - Visual system architecture diagram (draw.io)
```

## System Architecture Diagram

The file `documentation/diagrams/system-architecture.drawio` is a draw.io diagram showing the full end-to-end system architecture: client layer, FastAPI server, concurrent workers (analysis engine + market updater), data layer (portfolio.py / redis_client.py), and Redis storage with Lua scripts.

**When making changes that affect the architecture, you must update this diagram:**

1. Open `documentation/diagrams/system-architecture.drawio` and modify the relevant components, arrows, or labels to reflect the new architecture.
2. Update the grey **"Maintainer: Claude (automated)"** note box (top-right of the diagram, cell id `PoARDayDRui8yD0Vx3xu-2`) to include:
   - **Last updated:** the date/time of the change (ISO format, e.g. `2026-02-26T14:30Z`)
   - **Last commit:** the short SHA of the commit that triggered the update
   - **Assisted by:** who made the change (e.g. `Claude Opus 4.6`, `human`, or both)
3. The note box value should follow this format:
   ```
   Maintainer: Claude (automated)

   Last updated: <ISO datetime>
   Last commit: <short SHA>
   Assisted by: <who>

   Note: This is only intended as a code test
   ```

## Running

```bash
# Redis (requires Redis 8+ with JSON module)
docker run -d --name redis -p 6379:6379 redis:latest

# Server
pip install -r requirements.txt
uvicorn app.main:app --reload --reload-dir app

# Demo client
python scripts/demo_client.py
```

## Code Conventions

- Type hints everywhere (Python 3.10+ union syntax: `X | None`)
- Pydantic models for all serialization boundaries
- `async`/`await` throughout — no blocking calls
- Lua scripts are inline strings in `redis_client.py`, registered via `EVALSHA` at startup
- Behavioral config in `config.json` structured by feature; deployment config (`redis_url`) via env vars with `PORTFOLIO_` prefix (see `app/config.py` and ADR-003)

## Important Constraints

- **Never decode full JSON in Lua when a path query suffices** — use `JSON.GET key $.path` instead of `cjson.decode(redis.call('GET', key))`
- **Never write to Redis without refreshing TTL** — every mutation must call `EXPIRE`
- **Analysis results must use the snapshot taken at analysis start** — do not re-read portfolio state mid-analysis
- **Cancelled tasks must exit cleanly** — catch `asyncio.CancelledError`, do not write partial results
- Portfolio state mutations go through `redis_client.py` Lua scripts — never write to Redis directly from application code
- The `portfolio.py` module is the public Python API for state operations — other modules should not import from `redis_client.py`
- Read `documentation/adr/001-system-architecture.md` before making architectural changes
- Test against a real Redis 8+ instance with the JSON module loaded
