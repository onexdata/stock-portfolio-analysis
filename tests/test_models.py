"""Tests for Pydantic models — defaults, validation, and serialization."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from app.models import (
    AnalysisResultMessage,
    AnalyzeRequest,
    ErrorMessage,
    PortfolioState,
)


def test_portfolio_state_defaults():
    state = PortfolioState(session_id="s1")
    assert state.holdings == {"AAPL": 100, "GOOGL": 50, "MSFT": 75}
    assert state.total_value == 125000.00
    assert state.current_analysis is None
    assert state.analysis_results == []


def test_portfolio_state_holdings_independent():
    """default_factory creates a fresh dict per instance."""
    a = PortfolioState(session_id="a")
    b = PortfolioState(session_id="b")
    a.holdings["TSLA"] = 10
    assert "TSLA" not in b.holdings


def test_portfolio_state_json_roundtrip():
    original = PortfolioState(session_id="rt")
    json_str = original.model_dump_json()
    restored = PortfolioState.model_validate_json(json_str)
    assert restored == original


def test_analyze_request_valid():
    req = AnalyzeRequest(action="analyze", ticker="AAPL")
    assert req.action == "analyze"
    assert req.ticker == "AAPL"


def test_analyze_request_missing_ticker():
    with pytest.raises(ValidationError):
        AnalyzeRequest(action="analyze")


def test_analysis_result_message_default_type():
    msg = AnalysisResultMessage(
        ticker="AAPL", metric="risk", value=0.5, timestamp=datetime.utcnow()
    )
    assert msg.type == "analysis_result"


def test_error_message_default_type():
    msg = ErrorMessage(detail="something broke")
    assert msg.type == "error"
