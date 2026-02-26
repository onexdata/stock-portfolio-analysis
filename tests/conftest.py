"""Shared fixtures for the test suite."""

import pytest

from app.models import PortfolioState


@pytest.fixture
def sample_state() -> PortfolioState:
    return PortfolioState(session_id="test-session")


@pytest.fixture
def sample_state_json(sample_state: PortfolioState) -> str:
    return sample_state.model_dump_json()
