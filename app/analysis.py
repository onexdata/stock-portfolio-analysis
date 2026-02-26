"""Parallel metric computation engine with cancellation support."""

import asyncio
import random
from datetime import datetime, timezone
from typing import Callable, Awaitable

from app.models import PortfolioState, MetricResult, AnalysisResultMessage
from app import portfolio
from app.config import settings


# ── Mock metric computation ──────────────────────────────────────────────────
# Each function simulates 2-5 seconds of work and returns a float value
# derived from the portfolio snapshot so results are deterministic-ish.

def _holding_weight(ticker: str, state: PortfolioState) -> float:
    """Fraction of portfolio in this ticker (by share count)."""
    total_shares = sum(state.holdings.values()) or 1
    return state.holdings.get(ticker, 0) / total_shares


async def _compute_portfolio_risk(ticker: str, state: PortfolioState) -> float:
    await asyncio.sleep(random.uniform(2, 5))
    weight = _holding_weight(ticker, state)
    return round(weight * random.uniform(0.1, 0.5), 4)


async def _compute_concentration(ticker: str, state: PortfolioState) -> float:
    await asyncio.sleep(random.uniform(2, 5))
    return round(_holding_weight(ticker, state), 4)


async def _compute_correlation(ticker: str, state: PortfolioState) -> float:
    await asyncio.sleep(random.uniform(2, 5))
    return round(random.uniform(-0.3, 0.9), 4)


async def _compute_momentum(ticker: str, state: PortfolioState) -> float:
    await asyncio.sleep(random.uniform(2, 5))
    weight = _holding_weight(ticker, state)
    return round(random.uniform(-1, 1) * weight, 4)


async def _compute_allocation_score(ticker: str, state: PortfolioState) -> float:
    await asyncio.sleep(random.uniform(2, 5))
    weight = _holding_weight(ticker, state)
    # Score > 0 = increase position, < 0 = decrease
    ideal = 1.0 / max(len(state.holdings), 1)
    return round(ideal - weight, 4)


_METRIC_FNS: dict[str, Callable] = {
    "portfolio_risk": _compute_portfolio_risk,
    "concentration": _compute_concentration,
    "correlation": _compute_correlation,
    "momentum": _compute_momentum,
    "allocation_score": _compute_allocation_score,
}


# ── Analysis runner ──────────────────────────────────────────────────────────

async def _run_single_metric(
    session_id: str,
    ticker: str,
    metric: str,
    snapshot: PortfolioState,
    on_result: Callable[[AnalysisResultMessage], Awaitable[None]],
) -> None:
    """Compute one metric, persist it, and stream it to the client."""
    compute_fn = _METRIC_FNS[metric]
    value = await compute_fn(ticker, snapshot)

    now = datetime.now(timezone.utc)
    result = MetricResult(
        ticker=ticker, metric=metric, value=value, timestamp=now,
    )

    # Persist atomically via Lua script
    await portfolio.append_result(session_id, result)

    # Stream to client
    msg = AnalysisResultMessage(
        ticker=ticker, metric=metric, value=value, timestamp=now,
    )
    await on_result(msg)


async def run_analysis(
    session_id: str,
    ticker: str,
    snapshot: PortfolioState,
    on_result: Callable[[AnalysisResultMessage], Awaitable[None]],
) -> None:
    """Launch all metrics in parallel for the given ticker.

    Uses the provided snapshot so all metrics see the same portfolio state.
    Caller is responsible for wrapping this in a Task and cancelling it on
    ticker switch.
    """
    tasks = [
        asyncio.create_task(
            _run_single_metric(session_id, ticker, metric, snapshot, on_result)
        )
        for metric in settings.analysis_metrics
    ]
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        # Cancel any remaining sub-tasks cleanly
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        raise
