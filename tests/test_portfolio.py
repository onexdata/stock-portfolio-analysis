"""Tests for the portfolio CRUD layer — redis_client boundary mocking."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from app.models import PortfolioState
from app import portfolio


@pytest.fixture
def state() -> PortfolioState:
    return PortfolioState(session_id="test-session")


async def test_ensure_session_calls_init(state):
    """init_session is called with session_id and valid JSON."""
    with patch("app.portfolio.redis_client") as mock_rc:
        mock_rc.init_session = AsyncMock(return_value=state.model_dump_json())
        result = await portfolio.ensure_session("test-session")

    mock_rc.init_session.assert_called_once()
    call_args = mock_rc.init_session.call_args
    assert call_args[0][0] == "test-session"
    # Second arg should be valid JSON that deserializes to a PortfolioState
    PortfolioState.model_validate_json(call_args[0][1])


async def test_ensure_session_returns_portfolio_state(state):
    with patch("app.portfolio.redis_client") as mock_rc:
        mock_rc.init_session = AsyncMock(return_value=state.model_dump_json())
        result = await portfolio.ensure_session("test-session")

    assert isinstance(result, PortfolioState)
    assert result.session_id == "test-session"


async def test_get_portfolio_returns_none_when_missing():
    with patch("app.portfolio.redis_client") as mock_rc:
        mock_rc.get_portfolio = AsyncMock(return_value=None)
        result = await portfolio.get_portfolio("nonexistent")

    assert result is None


async def test_start_analysis_passes_ticker(state):
    with patch("app.portfolio.redis_client") as mock_rc:
        mock_rc.start_analysis = AsyncMock(return_value=state.model_dump_json())
        await portfolio.start_analysis("test-session", "AAPL")

    mock_rc.start_analysis.assert_called_once()
    call_args = mock_rc.start_analysis.call_args
    # First positional arg is session_id
    assert call_args[0][0] == "test-session"
    # Second arg is JSON containing the ticker
    analysis_json = json.loads(call_args[0][1])
    assert analysis_json["ticker"] == "AAPL"


async def test_update_market_values_serializes_prices(state):
    prices = {"AAPL": 186.50, "GOOGL": 141.20}
    with patch("app.portfolio.redis_client") as mock_rc:
        mock_rc.update_market = AsyncMock(return_value=state.model_dump_json())
        await portfolio.update_market_values("test-session", prices)

    mock_rc.update_market.assert_called_once()
    call_args = mock_rc.update_market.call_args
    assert call_args[0][0] == "test-session"
    # Second arg is json.dumps(prices)
    assert json.loads(call_args[0][1]) == prices
