# ADR-001: System Architecture

**Status:** Proposed
**Date:** 2026-02-26

## Context

We need a backend service that provides real-time stock portfolio analysis. The system supports multiple concurrent portfolio sessions with isolated state. Clients connect, request analysis on stocks, and receive streaming results. Three concurrent operations modify shared state (client requests, analysis completions, market updates), and the system must maintain consistency across all of them.

Key constraints from the requirements:
- Persistent client connections with bidirectional messaging
- Redis for state storage (required)
- Python 3.10+ / FastAPI / asyncio
- 5 metrics computed in parallel per analysis (2-5s each)
- Background market updates every 30 seconds
- 24-hour session expiry on inactivity
- Stale portfolio data in analysis results is unacceptable

## Decision

### Architecture Overview

```
Client (WebSocket)
    |
    v
FastAPI WebSocket endpoint
    |
    +---> Portfolio state (RedisJSON + Lua scripts)
    |
    +---> Analysis engine (asyncio.gather with cancellation)
    |
    +---> Background market updater (periodic task)
```

Four components cooperate through Redis as the single source of truth:

1. **FastAPI + WebSockets** — real-time bidirectional client communication
2. **RedisJSON + Lua scripts** — native JSON document storage with atomic multi-path operations
3. **asyncio tasks** — parallel metric computation with cancellation support
4. **Background scheduler** — periodic market data updates

### Project Structure

```
app/
  main.py           - FastAPI app, WebSocket endpoint, lifespan
  models.py         - Pydantic models for messages and state
  redis_client.py   - Redis connection + Lua script helpers
  portfolio.py      - Portfolio state CRUD via Redis
  analysis.py       - Parallel metric computation engine
  market.py         - Background market data updater
  config.py         - Settings
scripts/
  demo_client.py    - WebSocket test/demo script
documentation/
  adr/
    001-system-architecture.md
```

## Key Decisions

### 1. WebSockets over Server-Sent Events

**Choice:** WebSockets for client-server communication.

**Rationale:** The protocol is inherently bidirectional — clients send `{"action": "analyze", "ticker": "AAPL"}` requests AND receive streaming `{"type": "analysis_result", ...}` responses over the same connection. SSE only supports server-to-client; we'd need a separate HTTP endpoint for client commands, adding complexity for no benefit.

### 2. RedisJSON + Lua Hybrid over Plain Strings with Lua

**Choice:** Store portfolio state as a native RedisJSON document. Use direct `JSON.SET`/`JSON.GET` for simple operations; wrap multi-step mutations in Lua scripts that call JSON commands internally.

**Rationale:** Three concurrent operations modify the same portfolio state object:
- Client requests update `current_analysis` and `last_activity`
- Analysis results append to `analysis_results`
- Market updates recalculate `total_value`

#### Why not WATCH/MULTI?

With `WATCH/MULTI`, any concurrent write causes the transaction to fail, requiring retry loops. Under load (5 metrics completing near-simultaneously + market updates), retries cascade.

#### Why RedisJSON over plain strings?

The original approach used Lua scripts with `cjson.decode`/`cjson.encode` on plain string keys — every mutation decoded the entire JSON document, modified it, re-encoded, and wrote the whole blob back. This works but has two problems:

1. **O(n) appends** — every `analysis_results` append decodes and re-encodes the growing array. With RedisJSON, `JSON.ARRAPPEND` is O(1) regardless of array size.
2. **Full-document overhead** — market updates only need `$.holdings` to compute a new total, but the plain-string approach decodes the entire document including all historical results. RedisJSON path queries (`JSON.GET key $.holdings`) read only the data needed.

Redis 8 ships RedisJSON as a built-in module (no separate installation). Since this is a greenfield project targeting Redis 8, there's no portability concern.

#### The hybrid split

| Operation | Approach | Why |
|---|---|---|
| `init_session` | Direct `JSON.SET ... NX` | Single command with NX flag, no multi-step logic |
| `get_portfolio` | Direct `JSON.GET` + `EXPIRE` | Simple read, no atomicity needed beyond single commands |
| `start_analysis` | Lua calling `JSON.SET` on two paths | Must set `$.current_analysis` and `$.last_activity` atomically and return the full snapshot |
| `append_result` | Lua calling `JSON.ARRAPPEND` + `JSON.SET` | Must append result and update `$.last_activity` atomically — **O(1) append** |
| `update_market` | Lua reading `$.holdings`, computing total, writing `$.total_value` | Cross-path computation that can't be expressed as a single JSON command |

Lua scripts execute atomically on the Redis server — a single round-trip performs the multi-step mutation with no possibility of conflict. But inside those scripts, we use JSON path commands instead of decoding/encoding the entire document.

#### Trade-offs vs plain strings + Lua

| | Plain strings + Lua | RedisJSON + Lua hybrid |
|---|---|---|
| Append to array | O(n) decode + encode | O(1) `JSON.ARRAPPEND` |
| Partial reads | Must decode full blob | Path query reads only what's needed |
| Memory per key | Lower (raw string) | Higher (deserialized tree structure) |
| Portability | Any Redis version | Redis 8+ with JSON module |
| Full-document SET | Faster (no parse into tree) | Slightly slower (builds internal tree) |

The memory overhead is negligible for our document sizes (~1-5KB per session). The portability constraint is acceptable — this is greenfield targeting Redis 8.

### 3. Cancel-on-Switch

**Choice:** When a user requests analysis on a new ticker, cancel all in-flight metric computations for the previous ticker.

**Rationale:** The requirements state users "will switch between different stocks to understand different positions." If a user switches from AAPL to GOOGL, continuing to compute AAPL metrics wastes resources and could confuse the client with interleaved results from both tickers.

**Implementation:** Each WebSocket session holds a reference to its current `asyncio.Task` group. On a new `analyze` request:
1. Cancel the existing task group (if any) via `task.cancel()`
2. Start a new task group for the requested ticker
3. Cancelled tasks catch `asyncio.CancelledError` and exit cleanly — no partial results are written

### 4. Snapshot Consistency for Analysis

**Choice:** Read portfolio state once at the start of analysis; all 5 metrics use that snapshot.

**Rationale:** The requirements state "analysis results drive investment decisions — returning analysis computed with stale portfolio values is unacceptable." This creates a tension:

- If we re-read state per metric, different metrics could see different portfolio compositions (e.g., `total_value` changes mid-analysis from a market update), producing an internally inconsistent set of results.
- If we snapshot once, all 5 metrics are computed against the same portfolio state, guaranteeing internal consistency.

**Trade-off:** A market update that lands 1 second into a ~5 second analysis cycle won't be reflected in that cycle's results. This is acceptable because:
- Market updates happen every 30s; analysis takes 2-5s. The window for staleness is small.
- Internal consistency (all metrics agree on portfolio composition) matters more for investment decisions than absolute recency.
- The next analysis request will use fresh data.

The snapshot is taken via a Lua script that reads the full portfolio state and sets `current_analysis` atomically — no other operation can modify the state between the read and the analysis-start marker.

### 5. Session TTL with Activity Refresh

**Choice:** Redis key expiry at 24 hours, refreshed on every client interaction.

**Rationale:** The requirements specify "portfolio sessions should expire after 24 hours of inactivity." Redis native `EXPIRE` handles this cleanly:

- Every Lua script that modifies state also calls `EXPIRE` on the key, resetting the 24-hour clock
- If a client disconnects and never returns, Redis automatically reclaims the memory
- No background cleanup job needed

## Consequences

### Positive
- RedisJSON hybrid eliminates full decode/encode overhead — `JSON.ARRAPPEND` is O(1), path queries read only needed fields
- Lua scripts eliminate all race conditions for multi-step mutations — no retry logic, no optimistic locking
- Simple operations (init, get) use direct JSON commands — no Lua overhead for reads
- Cancel-on-switch prevents resource waste and result interleaving
- Snapshot consistency guarantees internally coherent analysis results
- Session TTL is zero-maintenance via Redis native expiry

### Negative
- Requires Redis 8+ with the JSON module loaded (acceptable for greenfield; Docker `redis:latest` ships it by default)
- Slightly higher memory per key than plain strings (RedisJSON's internal tree structure)
- Lua scripts are harder to unit test than pure Python — we'll need integration tests with a real Redis instance
- Cancel-on-switch means users can't compare two in-flight analyses simultaneously (not a stated requirement)
- Snapshot consistency means a market update mid-analysis won't be reflected until the next analysis run

### Risks
- Redis is a single point of failure (acceptable for a take-home project; in production, use Redis Sentinel or Cluster)
- Lua script complexity could grow if more operations are added (mitigated by keeping each script focused on one operation)
- `cjson` in Lua cannot distinguish JSON `null` from Lua `nil` — not an issue for our schema but worth noting for future extensions
