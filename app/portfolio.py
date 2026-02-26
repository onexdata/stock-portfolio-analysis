"""Portfolio state CRUD — thin Python layer over RedisJSON + Lua scripts."""

import json
from datetime import datetime, timezone

from app.models import PortfolioState, CurrentAnalysis, MetricResult
from app import redis_client


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _json_quote(s: str) -> str:
    """Wrap a string value in JSON quotes for use in JSON.SET."""
    return json.dumps(s)


async def ensure_session(session_id: str) -> PortfolioState:
    """Create a session if it doesn't exist, return current state."""
    initial = PortfolioState(session_id=session_id)
    raw = await redis_client.init_session(
        session_id, initial.model_dump_json()
    )
    return PortfolioState.model_validate_json(raw)


async def get_portfolio(session_id: str) -> PortfolioState | None:
    """Read current portfolio state (refreshes TTL)."""
    raw = await redis_client.get_portfolio(session_id)
    if raw is None:
        return None
    return PortfolioState.model_validate_json(raw)


async def start_analysis(session_id: str, ticker: str) -> PortfolioState | None:
    """Mark a new analysis as started and return the state snapshot."""
    now = _now()
    current = CurrentAnalysis(ticker=ticker, started_at=now)
    raw = await redis_client.start_analysis(
        session_id,
        current.model_dump_json(),
        _json_quote(now.isoformat()),
    )
    if raw is None:
        return None
    return PortfolioState.model_validate_json(raw)


async def append_result(session_id: str, result: MetricResult) -> PortfolioState | None:
    """Append a completed metric result to the portfolio."""
    now = _now()
    raw = await redis_client.append_result(
        session_id,
        result.model_dump_json(),
        _json_quote(now.isoformat()),
    )
    if raw is None:
        return None
    return PortfolioState.model_validate_json(raw)


async def update_market_values(
    session_id: str, prices: dict[str, float]
) -> PortfolioState | None:
    """Recalculate total_value from latest prices."""
    now = _now()
    raw = await redis_client.update_market(
        session_id,
        json.dumps(prices),
        _json_quote(now.isoformat()),
    )
    if raw is None:
        return None
    return PortfolioState.model_validate_json(raw)
