"""Background market data updater — simulates periodic price changes."""

import asyncio
import logging
import random

from app import redis_client, portfolio
from app.config import config

_market = config.features.market_updates.settings

logger = logging.getLogger(__name__)

def _mock_prices(tickers: list[str]) -> dict[str, float]:
    """Generate mock prices with random walk from base (volatility from config)."""
    prices = {}
    for ticker in tickers:
        base = _market.base_prices.get(ticker, _market.default_price)
        jitter = base * random.uniform(-_market.volatility, _market.volatility)
        prices[ticker] = round(base + jitter, 2)
    return prices


async def market_update_loop() -> None:
    """Run forever, updating all active portfolio sessions every interval."""
    logger.info(
        "Market updater started (interval=%ss)",
        _market.interval_seconds,
    )
    while True:
        try:
            await asyncio.sleep(_market.interval_seconds)
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
