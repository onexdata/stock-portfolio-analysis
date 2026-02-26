"""Background market data updater — simulates periodic price changes."""

import asyncio
import logging
import random

from app import redis_client, portfolio
from app.config import settings

logger = logging.getLogger(__name__)

# Base prices for mock data (rough real-world magnitudes)
_BASE_PRICES: dict[str, float] = {
    "AAPL": 185.0,
    "GOOGL": 140.0,
    "MSFT": 375.0,
    "AMZN": 155.0,
    "TSLA": 200.0,
    "META": 390.0,
    "NVDA": 650.0,
}

_DEFAULT_PRICE = 100.0


def _mock_prices(tickers: list[str]) -> dict[str, float]:
    """Generate mock prices with +/- 2% random walk from base."""
    prices = {}
    for ticker in tickers:
        base = _BASE_PRICES.get(ticker, _DEFAULT_PRICE)
        jitter = base * random.uniform(-0.02, 0.02)
        prices[ticker] = round(base + jitter, 2)
    return prices


async def market_update_loop() -> None:
    """Run forever, updating all active portfolio sessions every interval."""
    logger.info(
        "Market updater started (interval=%ss)",
        settings.market_update_interval_seconds,
    )
    while True:
        try:
            await asyncio.sleep(settings.market_update_interval_seconds)
            keys = await redis_client.get_all_session_keys()
            for key in keys:
                # key format: "portfolio:<session_id>"
                session_id = key.split(":", 1)[1]
                state = await portfolio.get_portfolio(session_id)
                if state is None:
                    continue
                tickers = list(state.holdings.keys())
                if not tickers:
                    continue
                prices = _mock_prices(tickers)
                await portfolio.update_market_values(session_id, prices)
                logger.debug(
                    "Updated market values for session %s: total=%.2f",
                    session_id,
                    sum(prices[t] * state.holdings[t] for t in tickers),
                )
        except asyncio.CancelledError:
            logger.info("Market updater stopped")
            raise
        except Exception:
            logger.exception("Error in market update loop")
