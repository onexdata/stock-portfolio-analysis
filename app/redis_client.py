import json

import redis.asyncio as redis

from app.config import settings

# ── Connection ───────────────────────────────────────────────────────────────

_pool: redis.Redis | None = None


async def get_redis() -> redis.Redis:
    global _pool
    if _pool is None:
        _pool = redis.from_url(settings.redis_url, decode_responses=True)
    return _pool


async def close_redis() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None


# ── Key helpers ──────────────────────────────────────────────────────────────

def _key(session_id: str) -> str:
    return f"portfolio:{session_id}"


# ── Direct RedisJSON operations ──────────────────────────────────────────────
# Simple operations that don't need multi-step atomicity use JSON.SET/JSON.GET
# directly — no Lua overhead.


async def init_session(session_id: str, state_json: str) -> str | None:
    """Create session if it doesn't exist (NX), refresh TTL, return state."""
    r = await get_redis()
    key = _key(session_id)
    try:
        # NX = only set if key does not exist
        await r.execute_command("JSON.SET", key, "$", state_json, "NX")
    except redis.ResponseError as e:
        if "wrong Redis type" in str(e) or "WRONGTYPE" in str(e):
            # Stale key from a previous run stored as a different type — replace it
            await r.delete(key)
            await r.execute_command("JSON.SET", key, "$", state_json)
        else:
            raise
    await r.expire(key, settings.session_ttl_seconds)
    raw = await r.execute_command("JSON.GET", key)
    return raw


async def get_portfolio(session_id: str) -> str | None:
    """Read full portfolio state and refresh TTL."""
    r = await get_redis()
    key = _key(session_id)
    raw = await r.execute_command("JSON.GET", key)
    if raw is not None:
        await r.expire(key, settings.session_ttl_seconds)
    return raw


# ── Lua scripts (hybrid: Lua wrapping JSON commands) ─────────────────────────
# Multi-step operations that need atomicity use Lua scripts, but call
# JSON.SET / JSON.GET / JSON.ARRAPPEND internally instead of cjson
# decode/encode of the entire document.

# Sets current_analysis and last_activity atomically. Returns full state
# snapshot so the caller can use it for analysis.
# KEYS[1] = portfolio:<session_id>
# ARGV[1] = JSON object for current_analysis, e.g. {"ticker":"AAPL","started_at":"..."}
# ARGV[2] = ISO timestamp string (quoted for JSON)
# ARGV[3] = TTL in seconds
START_ANALYSIS = """
local exists = redis.call('JSON.TYPE', KEYS[1], '$')
if not exists or exists[1] == false then return nil end

redis.call('JSON.SET', KEYS[1], '$.current_analysis', ARGV[1])
redis.call('JSON.SET', KEYS[1], '$.last_activity', ARGV[2])
redis.call('EXPIRE', KEYS[1], ARGV[3])
return redis.call('JSON.GET', KEYS[1])
"""

# Appends one metric result to analysis_results and updates last_activity.
# O(1) append via JSON.ARRAPPEND — no decode of the full array.
# KEYS[1] = portfolio:<session_id>
# ARGV[1] = JSON of MetricResult
# ARGV[2] = ISO timestamp string (quoted for JSON)
# ARGV[3] = TTL in seconds
APPEND_RESULT = """
local exists = redis.call('JSON.TYPE', KEYS[1], '$')
if not exists or exists[1] == false then return nil end

redis.call('JSON.ARRAPPEND', KEYS[1], '$.analysis_results', ARGV[1])
redis.call('JSON.SET', KEYS[1], '$.last_activity', ARGV[2])
redis.call('EXPIRE', KEYS[1], ARGV[3])
return redis.call('JSON.GET', KEYS[1])
"""

# Recalculates total_value from new prices. Reads only $.holdings (not the
# full document), computes the new total, then writes back $.total_value.
# KEYS[1] = portfolio:<session_id>
# ARGV[1] = JSON object mapping ticker -> price
# ARGV[2] = ISO timestamp string (quoted for JSON)
# ARGV[3] = TTL in seconds
UPDATE_MARKET = """
local raw_holdings = redis.call('JSON.GET', KEYS[1], '$.holdings')
if not raw_holdings then return nil end

local holdings_arr = cjson.decode(raw_holdings)
local holdings = holdings_arr[1]
local prices = cjson.decode(ARGV[1])

local total = 0
for ticker, qty in pairs(holdings) do
    local price = prices[ticker]
    if price then
        total = total + (price * qty)
    end
end

redis.call('JSON.SET', KEYS[1], '$.total_value', tostring(total))
redis.call('JSON.SET', KEYS[1], '$.last_activity', ARGV[2])
redis.call('EXPIRE', KEYS[1], ARGV[3])
return redis.call('JSON.GET', KEYS[1])
"""

# Pre-registered script objects (set during startup)
_scripts: dict[str, object] = {}


async def register_scripts() -> None:
    """Register Lua scripts with Redis so they run via EVALSHA."""
    r = await get_redis()
    _scripts["start_analysis"] = r.register_script(START_ANALYSIS)
    _scripts["append_result"] = r.register_script(APPEND_RESULT)
    _scripts["update_market"] = r.register_script(UPDATE_MARKET)


# ── Lua-backed public helpers ────────────────────────────────────────────────

async def start_analysis(
    session_id: str, current_analysis_json: str, timestamp_json: str,
) -> str | None:
    return await _scripts["start_analysis"](
        keys=[_key(session_id)],
        args=[current_analysis_json, timestamp_json, settings.session_ttl_seconds],
    )


async def append_result(
    session_id: str, result_json: str, timestamp_json: str,
) -> str | None:
    return await _scripts["append_result"](
        keys=[_key(session_id)],
        args=[result_json, timestamp_json, settings.session_ttl_seconds],
    )


async def update_market(
    session_id: str, prices_json: str, timestamp_json: str,
) -> str | None:
    return await _scripts["update_market"](
        keys=[_key(session_id)],
        args=[prices_json, timestamp_json, settings.session_ttl_seconds],
    )


async def get_all_session_keys() -> list[str]:
    """Return all active portfolio session keys (for market updater)."""
    r = await get_redis()
    keys = []
    async for key in r.scan_iter(match="portfolio:*"):
        keys.append(key)
    return keys
