"""Shared fixtures for the test suite."""

from unittest.mock import AsyncMock, patch

import pytest

from app.models import PortfolioState


@pytest.fixture
def sample_state() -> PortfolioState:
    return PortfolioState(session_id="test-session")


@pytest.fixture
def sample_state_json(sample_state: PortfolioState) -> str:
    return sample_state.model_dump_json()


@pytest.fixture
def mock_redis():
    """Patch redis_client functions used by portfolio and market modules."""
    with (
        patch("app.portfolio.redis_client") as portfolio_rc,
        patch("app.market.redis_client") as market_rc,
    ):
        # Make all methods async by default
        for attr in [
            "init_session",
            "get_portfolio",
            "start_analysis",
            "append_result",
            "update_market",
            "get_all_session_keys",
        ]:
            setattr(portfolio_rc, attr, AsyncMock())
            setattr(market_rc, attr, AsyncMock())

        yield {"portfolio": portfolio_rc, "market": market_rc}
