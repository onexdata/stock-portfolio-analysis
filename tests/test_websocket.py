"""Tests for the FastAPI app — health check, WebSocket connect, and message handling."""

import asyncio
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.models import PortfolioState


@pytest.fixture
def sample_state() -> PortfolioState:
    return PortfolioState(session_id="test-session")


@pytest.fixture
def client(sample_state):
    """TestClient with the lifespan and redis fully mocked out."""
    with (
        patch("app.main.redis_client") as mock_rc,
        patch("app.main.portfolio") as mock_portfolio,
        patch("app.main.run_analysis", new_callable=AsyncMock) as mock_run,
        patch("app.main.market_update_loop", new_callable=AsyncMock) as mock_market,
    ):
        mock_rc.get_redis = AsyncMock()
        mock_rc.register_scripts = AsyncMock()
        mock_rc.close_redis = AsyncMock()

        mock_portfolio.ensure_session = AsyncMock(return_value=sample_state)
        mock_portfolio.start_analysis = AsyncMock(return_value=sample_state)

        from app.main import app

        with TestClient(app) as c:
            yield {
                "client": c,
                "portfolio": mock_portfolio,
                "run_analysis": mock_run,
                "market_loop": mock_market,
            }


def test_health_endpoint(client):
    resp = client["client"].get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_websocket_connects(client):
    with client["client"].websocket_connect("/ws/test-session") as ws:
        pass  # Handshake succeeds
    client["portfolio"].ensure_session.assert_called_with("test-session")


def test_websocket_invalid_message_returns_error(client):
    with client["client"].websocket_connect("/ws/test-session") as ws:
        ws.send_json({"action": "analyze"})  # missing ticker
        resp = ws.receive_json()
    assert resp["type"] == "error"
    assert "Invalid message" in resp["detail"] or "ticker" in resp["detail"].lower()


def test_websocket_unknown_action_returns_error(client):
    with client["client"].websocket_connect("/ws/test-session") as ws:
        ws.send_json({"action": "delete", "ticker": "AAPL"})
        resp = ws.receive_json()
    assert resp["type"] == "error"
    assert "Unknown action" in resp["detail"]


def test_websocket_analyze_starts_analysis(client):
    with client["client"].websocket_connect("/ws/test-session") as ws:
        ws.send_json({"action": "analyze", "ticker": "AAPL"})
        # Give the background task a moment to be created
        import time
        time.sleep(0.1)

    client["portfolio"].start_analysis.assert_called_once_with("test-session", "AAPL")
    client["run_analysis"].assert_called_once()
    call_args = client["run_analysis"].call_args
    assert call_args[0][0] == "test-session"  # session_id
    assert call_args[0][1] == "AAPL"  # ticker
