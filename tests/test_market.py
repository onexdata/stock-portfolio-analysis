"""Tests for the market data module — mock price generation."""

import pytest

from app.market import _mock_prices


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
