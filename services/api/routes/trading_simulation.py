from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, status

from libs.cache import MarketQuoteCache
from libs.config import get_settings
from libs.domain.market import Market, MarketQuote
from services.api.schemas.trading_simulation import (
    SimulatedTradingQuoteRequest,
    SimulatedTradingQuoteResponse,
)

router = APIRouter(
    prefix="/api/v1/trading/simulation",
    tags=["trading-simulation"],
)


def _require_local_environment() -> None:
    settings = get_settings()

    if not settings.is_local:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="not found",
        )


@router.get(
    "/quote/{symbol}",
    response_model=SimulatedTradingQuoteResponse,
)
def get_simulated_quote(
    symbol: str,
) -> SimulatedTradingQuoteResponse:
    _require_local_environment()

    quote = MarketQuoteCache().get_quote(
        market=Market.US,
        symbol=symbol,
    )

    if quote is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="simulated quote not found",
        )

    return SimulatedTradingQuoteResponse.from_domain(
        quote
    )


@router.post(
    "/quote",
    response_model=SimulatedTradingQuoteResponse,
    status_code=status.HTTP_201_CREATED,
)
def set_simulated_quote(
    request: SimulatedTradingQuoteRequest,
) -> SimulatedTradingQuoteResponse:
    _require_local_environment()

    quote = MarketQuote(
        symbol=request.symbol,
        market=Market.US,
        bid_price=request.bid_price,
        ask_price=request.ask_price,
        bid_size=request.bid_size,
        ask_size=request.ask_size,
        timestamp=datetime.now(UTC),
    )

    cache = MarketQuoteCache(
        ttl_seconds=request.ttl_seconds,
    )
    cache.set_quote(quote)

    return SimulatedTradingQuoteResponse.from_domain(
        quote
    )
