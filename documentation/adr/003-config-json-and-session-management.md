# ADR-003: Feature-Structured Config, Server Sessions, and Auto-Connect Frontend

**Status:** Proposed
**Date:** 2026-02-26

## Context

The application had configuration values hardcoded across multiple modules (`models.py`, `market.py`, `analysis.py`, `config.py`) and embedded in the frontend (`index.html`). Session IDs were client-generated UUIDs — verbose and not server-controlled. The frontend required manual "Connect" clicks, with no idle management or auto-reconnect.

These issues created three problems:

1. **Scattered config** — changing a default holding or base price required editing multiple source files
2. **Uncontrolled sessions** — the server had no say in session identity; any string could be used as a session ID
3. **Manual connection** — users had to click "Connect" on every page load and had no session lifecycle management

## Decision

### 1. Feature-Structured `config.json`

All behavioral configuration lives in a single `config.json` at the project root, structured by feature:

```json
{
  "app": { "name": "Portfolio Analysis" },
  "features": {
    "client-connectivity": { "enabled": true, "settings": { ... } },
    "client-ui": { "enabled": true, "settings": { ... } },
    "analysis": { "enabled": true, "settings": { ... } },
    "market-updates": { "enabled": true, "settings": { ... } }
  }
}
```

**Separation of concerns:**
- `config.json` — behavioral settings (holdings, prices, intervals, metrics)
- Environment variables (`PORTFOLIO_` prefix) — deployment settings (`redis_url` only)

**Implementation:** `app/config.py` uses a Pydantic model hierarchy with kebab-case alias generation (`_KebabModel` base class). JSON keys use `kebab-case`; Python attributes use `snake_case`. The config is loaded once at module import and exported as `config`. Environment settings are a separate `EnvSettings` object exported as `env`.

### 2. Server-Generated Compact Session IDs

A new `POST /session` endpoint generates session IDs on the server using the format `{prefix}-{timestamp}-{random}` (e.g., `s-1740600123-a7f3`). The endpoint:

- Generates a compact session ID using `time.time()` + `secrets.token_hex(2)`
- Initializes the portfolio in Redis via `portfolio.ensure_session()`
- Returns the session ID plus a filtered subset of config relevant to the client

**Client-relevant config** returned by `POST /session`:
- `client-connectivity.settings` — idle timeout, auto-reconnect (excludes TTL)
- `client-ui.settings` — theme, default holdings, initial value
- `analysis.settings.metrics` — metric names only (excludes simulation delays)

**Server-internal config** excluded from response:
- Session TTL, simulation delay range, base prices, volatility

### 3. Auto-Connect Frontend with Idle Timeout

The frontend no longer has a connection panel. On page load:

1. `createSession()` calls `POST /session`
2. Extracts config and builds the ticker grid from server-provided holdings
3. Opens a WebSocket using the server-provided session ID
4. Starts an idle timer based on `idle-timeout-seconds` from config

**Idle timeout behavior:**
- Timer resets on `click` and `keypress` events
- When idle timeout fires: close WebSocket, wait 1s, call `createSession()` for a new session
- Status badge in header shows "Connected" / "Reconnecting..." / "Connecting..."

## Consequences

### Positive
- Single file (`config.json`) controls all behavioral defaults — no source code changes needed to adjust values
- Server controls session identity — compact, predictable format for logging and debugging
- Auto-connect removes friction — users see data immediately on page load
- Idle timeout prevents stale sessions from accumulating
- Config is validated at startup by Pydantic — typos in `config.json` fail fast
- Falls back to sensible defaults if `config.json` is missing

### Negative
- `config.json` must be deployed alongside the application (not just environment variables)
- Server restart required to pick up config changes (no hot-reload)
- Idle timeout may surprise users who leave the tab open — mitigated by auto-reconnect creating a new session transparently

### Risks
- Feature `enabled` flags are not yet enforced at runtime — they're structural placeholders for future use
- Config file could grow large if many features are added — mitigated by the flat settings-per-feature structure
