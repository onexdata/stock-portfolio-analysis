"""Tests for the market data module — mock price generation and update loop."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.market import _mock_prices, market_update_loop
from app.models import PortfolioState


@pytest.mark.parametrize("_iteration", range(50))
def test_mock_prices_known_ticker_range(_iteration):
    """AAPL prices stay within 185.0 ± 2%."""
    prices = _mock_prices(["AAPL"])
    base = 185.0
    assert base * 0.98 <= prices["AAPL"] <= base * 1.02


def test_mock_prices_unknown_ticker_default():
    """Unknown tickers use the 100.0 default base ± 2%."""
    prices = _mock_prices(["XYZ"])
    base = 100.0
    assert base * 0.98 <= prices["XYZ"] <= base * 1.02


def test_mock_prices_rounds_to_two_decimals():
    prices = _mock_prices(["AAPL", "GOOGL", "MSFT"])
    for price in prices.values():
        assert price == round(price, 2)


def test_mock_prices_returns_all_requested_tickers():
    tickers = ["AAPL", "GOOGL", "MSFT", "TSLA"]
    prices = _mock_prices(tickers)
    assert set(prices.keys()) == set(tickers)


def test_mock_prices_empty_list():
    assert _mock_prices([]) == {}


async def test_market_update_loop_updates_session():
    """Smoke test: one iteration reads sessions, fetches state, updates prices."""
    state = PortfolioState(session_id="s1")
    iteration = 0

    async def sleep_then_cancel(duration):
        nonlocal iteration
        iteration += 1
        if iteration > 1:
            raise asyncio.CancelledError

    with (
        patch("app.market.asyncio.sleep", side_effect=sleep_then_cancel),
        patch("app.market.redis_client") as mock_rc,
        patch("app.market.portfolio") as mock_portfolio,
    ):
        mock_rc.get_all_session_keys = AsyncMock(return_value=["portfolio:s1"])
        mock_portfolio.get_portfolio = AsyncMock(return_value=state)
        mock_portfolio.update_market_values = AsyncMock()

        with pytest.raises(asyncio.CancelledError):
            await market_update_loop()

    mock_rc.get_all_session_keys.assert_called_once()
    mock_portfolio.get_portfolio.assert_called_once_with("s1")
    mock_portfolio.update_market_values.assert_called_once()
    call_args = mock_portfolio.update_market_values.call_args
    assert call_args[0][0] == "s1"
    prices = call_args[0][1]
    assert set(prices.keys()) == set(state.holdings.keys())
