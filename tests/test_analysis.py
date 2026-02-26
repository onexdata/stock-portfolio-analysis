"""Tests for the analysis engine — metric functions, orchestration, cancellation."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.analysis import (
    _holding_weight,
    _compute_allocation_score,
    _compute_concentration,
    _compute_correlation,
    _compute_momentum,
    _compute_portfolio_risk,
    run_analysis,
)
from app.models import AnalysisResultMessage, PortfolioState


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def state() -> PortfolioState:
    return PortfolioState(session_id="test")


# ── Pure function tests ──────────────────────────────────────────────────────


def test_holding_weight_known_ticker(state):
    # AAPL=100, GOOGL=50, MSFT=75 → total=225
    assert _holding_weight("AAPL", state) == pytest.approx(100 / 225)


def test_holding_weight_unknown_ticker(state):
    assert _holding_weight("TSLA", state) == 0.0


def test_holding_weight_empty_holdings():
    state = PortfolioState(session_id="empty", holdings={})
    assert _holding_weight("AAPL", state) == 0.0


async def test_concentration_equals_weight(state):
    """Concentration is deterministic — just the holding weight."""
    with patch("app.analysis.asyncio.sleep", new_callable=AsyncMock):
        result = await _compute_concentration("AAPL", state)
    assert result == pytest.approx(round(100 / 225, 4))


async def test_allocation_score_direction(state):
    """Underweight tickers get positive scores; overweight get negative."""
    with patch("app.analysis.asyncio.sleep", new_callable=AsyncMock):
        googl_score = await _compute_allocation_score("GOOGL", state)
        aapl_score = await _compute_allocation_score("AAPL", state)
    # ideal = 1/3 ≈ 0.3333; GOOGL weight = 50/225 ≈ 0.2222 (under), AAPL = 100/225 ≈ 0.4444 (over)
    assert googl_score > 0
    assert aapl_score < 0


# ── Orchestration tests ─────────────────────────────────────────────────────


async def test_run_analysis_all_five_metrics(state):
    results = []

    async def capture(msg: AnalysisResultMessage):
        results.append(msg)

    with (
        patch("app.analysis.asyncio.sleep", new_callable=AsyncMock),
        patch("app.analysis.portfolio.append_result", new_callable=AsyncMock),
    ):
        await run_analysis("s1", "AAPL", state, capture)

    assert len(results) == 5
    metric_names = {r.metric for r in results}
    assert metric_names == {
        "portfolio_risk",
        "concentration",
        "correlation",
        "momentum",
        "allocation_score",
    }


async def test_run_analysis_persists_results(state):
    with (
        patch("app.analysis.asyncio.sleep", new_callable=AsyncMock),
        patch("app.analysis.portfolio.append_result", new_callable=AsyncMock) as mock_append,
    ):
        await run_analysis("s1", "AAPL", state, AsyncMock())

    assert mock_append.call_count == 5


async def test_run_analysis_result_message_shape(state):
    results = []

    async def capture(msg: AnalysisResultMessage):
        results.append(msg)

    with (
        patch("app.analysis.asyncio.sleep", new_callable=AsyncMock),
        patch("app.analysis.portfolio.append_result", new_callable=AsyncMock),
    ):
        await run_analysis("s1", "AAPL", state, capture)

    for msg in results:
        assert isinstance(msg, AnalysisResultMessage)
        assert msg.ticker == "AAPL"
        assert msg.timestamp is not None
        assert isinstance(msg.value, float)


async def test_run_analysis_cancellation(state):
    """Cancelling mid-flight raises CancelledError with fewer than 5 results."""
    results = []
    call_count = 0

    async def slow_capture(msg: AnalysisResultMessage):
        nonlocal call_count
        call_count += 1
        results.append(msg)

    async def slow_sleep(duration):
        """Let the first metric through, then block so cancellation can hit."""
        if call_count >= 1:
            await asyncio.sleep(100)  # will be cancelled

    with (
        patch("app.analysis.asyncio.sleep", side_effect=slow_sleep),
        patch("app.analysis.portfolio.append_result", new_callable=AsyncMock),
    ):
        task = asyncio.create_task(
            run_analysis("s1", "AAPL", state, slow_capture)
        )
        # Give the first metric a chance to complete
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert len(results) < 5


# ── Randomized metric range tests ────────────────────────────────────────────


@pytest.mark.parametrize("_iteration", range(20))
async def test_metric_value_ranges(state, _iteration):
    weight = _holding_weight("AAPL", state)

    with patch("app.analysis.asyncio.sleep", new_callable=AsyncMock):
        risk = await _compute_portfolio_risk("AAPL", state)
        corr = await _compute_correlation("AAPL", state)
        mom = await _compute_momentum("AAPL", state)

    # portfolio_risk ∈ [0.1×weight, 0.5×weight] (weight * uniform(0.1, 0.5) rounded)
    assert 0.1 * weight - 1e-4 <= risk <= 0.5 * weight + 1e-4
    # correlation ∈ [-0.3, 0.9]
    assert -0.3 - 1e-4 <= corr <= 0.9 + 1e-4
    # momentum ∈ [-weight, weight]
    assert -weight - 1e-4 <= mom <= weight + 1e-4
