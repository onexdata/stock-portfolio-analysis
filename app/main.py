"""FastAPI app with WebSocket endpoint for real-time portfolio analysis."""

import asyncio
import logging

from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from app import redis_client, portfolio
from app.analysis import run_analysis
from app.market import market_update_loop
from app.models import AnalyzeRequest, AnalysisResultMessage, ErrorMessage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan ─────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await redis_client.get_redis()
    await redis_client.register_scripts()
    logger.info("Redis connected and Lua scripts registered")

    market_task = asyncio.create_task(market_update_loop())
    logger.info("Market updater background task started")

    yield

    # Shutdown
    market_task.cancel()
    try:
        await market_task
    except asyncio.CancelledError:
        pass
    await redis_client.close_redis()
    logger.info("Shutdown complete")


app = FastAPI(title="Portfolio Analysis", lifespan=lifespan)


# ── WebSocket endpoint ───────────────────────────────────────────────────────

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(ws: WebSocket, session_id: str):
    await ws.accept()
    logger.info("Client connected: session=%s", session_id)

    # Ensure portfolio state exists in Redis
    await portfolio.ensure_session(session_id)

    # Track the current analysis task so we can cancel-on-switch
    current_task: asyncio.Task | None = None

    try:
        while True:
            raw = await ws.receive_json()

            try:
                request = AnalyzeRequest(**raw)
            except Exception as e:
                await ws.send_json(
                    ErrorMessage(detail=f"Invalid message: {e}").model_dump()
                )
                continue

            if request.action != "analyze":
                await ws.send_json(
                    ErrorMessage(detail=f"Unknown action: {request.action}").model_dump()
                )
                continue

            ticker = request.ticker.upper()
            logger.info("Analyze request: session=%s ticker=%s", session_id, ticker)

            # ── Cancel-on-switch ─────────────────────────────────────────
            if current_task is not None and not current_task.done():
                logger.info("Cancelling in-flight analysis for session=%s", session_id)
                current_task.cancel()
                try:
                    await current_task
                except (asyncio.CancelledError, Exception):
                    pass

            # ── Snapshot + start ─────────────────────────────────────────
            snapshot = await portfolio.start_analysis(session_id, ticker)
            if snapshot is None:
                await ws.send_json(
                    ErrorMessage(detail="Session not found").model_dump()
                )
                continue

            # Callback that streams each result back over the WebSocket
            async def send_result(msg: AnalysisResultMessage) -> None:
                await ws.send_json(msg.model_dump(mode="json"))

            # Launch analysis as a background task
            current_task = asyncio.create_task(
                run_analysis(session_id, ticker, snapshot, send_result)
            )

    except WebSocketDisconnect:
        logger.info("Client disconnected: session=%s", session_id)
    except Exception:
        logger.exception("WebSocket error: session=%s", session_id)
    finally:
        # Clean up any in-flight analysis
        if current_task is not None and not current_task.done():
            current_task.cancel()
            try:
                await current_task
            except (asyncio.CancelledError, Exception):
                pass


# ── Health check ─────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok"}
