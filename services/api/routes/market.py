from __future__ import annotations

import re
from collections.abc import Generator
from typing import Annotated, NoReturn

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)

from libs.cache import get_redis_client
from libs.config import get_settings
from services.api.market_batch import BatchMarketQuoteService
from services.api.market_snapshot_cache import MarketSnapshotCache
from services.api.schemas.market import (
    MarketBatchQuoteResponse,
    MarketCandleItem,
    MarketCandleRange,
    MarketCandlesResponse,
    MarketPriceResponse,
    MarketQuoteResponse,
)
from services.market_ingestor.providers.twelve_data import (
    TwelveDataMarketDataProvider,
    TwelveDataRequestError,
    TwelveDataResponseError,
)

router = APIRouter(
    prefix="/api/v1/market",
    tags=["market"],
)


_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9.^-]{1,20}$")


_CANDLE_RANGE_CONFIG: dict[
    MarketCandleRange,
    tuple[str, int],
] = {
    "day": ("5min", 78),
    "week": ("1h", 40),
    "month": ("1day", 30),
}


def _normalize_symbol(symbol: str) -> str:
    """
    Normalize and validate a market symbol.

    Symbols are normalized to uppercase before validation so callers may
    safely provide values such as ``aapl`` or ``msft``.
    """

    normalized = symbol.strip().upper()

    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Symbol must not be empty.",
        )

    if not _SYMBOL_PATTERN.fullmatch(normalized):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid symbol format.",
        )

    return normalized


def _normalize_symbols(
    raw_symbols: str,
    *,
    max_symbols: int,
) -> list[str]:
    """
    Parse, normalize and de-duplicate a comma-separated symbol list.

    Ordering is preserved because the response order should follow the
    order selected by the user in the dashboard or watchlist.
    """

    result: list[str] = []
    seen: set[str] = set()

    for part in raw_symbols.split(","):
        normalized = _normalize_symbol(part)

        if normalized in seen:
            continue

        seen.add(normalized)
        result.append(normalized)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="At least one symbol is required.",
        )

    if len(result) > max_symbols:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "Too many symbols. "
                f"Maximum is {max_symbols}."
            ),
        )

    return result


def _resolve_candle_range(
    range_value: MarketCandleRange,
) -> tuple[str, int]:
    """
    Resolve the public chart range into a Twelve Data interval/output size.
    """

    return _CANDLE_RANGE_CONFIG[range_value]


def _raise_provider_request_error(
    exc: TwelveDataRequestError,
) -> NoReturn:
    """
    Translate an upstream transport/request failure into the stable API
    error contract exposed to clients.

    Provider implementation details are intentionally not leaked.
    """

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="market data provider request failed",
    ) from exc


def _raise_provider_response_error(
    exc: TwelveDataResponseError,
) -> NoReturn:
    """
    Translate malformed or invalid upstream data into the stable API
    error contract exposed to clients.

    Provider payload details are intentionally not leaked.
    """

    raise HTTPException(
        status_code=status.HTTP_502_BAD_GATEWAY,
        detail="market data provider response failed",
    ) from exc


def get_market_data_provider(
) -> Generator[
    TwelveDataMarketDataProvider,
    None,
    None,
]:
    """
    FastAPI dependency for the configured real-market provider.

    The provider owns its HTTP client for the lifetime of the request and
    is always closed after request processing finishes.
    """

    settings = get_settings()

    if settings.market_data_provider != "twelve_data":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="real market data provider is not enabled",
        )

    if settings.twelve_data_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Twelve Data API key is not configured",
        )

    provider = TwelveDataMarketDataProvider(
        api_key=settings.twelve_data_api_key,
    )

    try:
        yield provider
    finally:
        provider.close()


def get_market_snapshot_cache() -> MarketSnapshotCache:
    """
    Create the Redis-backed OHLC snapshot cache.

    This cache is deliberately separate from the existing bid/ask market
    quote cache.
    """

    settings = get_settings()

    return MarketSnapshotCache(
        get_redis_client(),
        fresh_ttl_seconds=(
            settings.market_quote_cache_ttl_seconds
        ),
        stale_ttl_seconds=(
            settings.market_quote_stale_ttl_seconds
        ),
    )


@router.get(
    "/price/{symbol}",
    response_model=MarketPriceResponse,
)
def read_market_price(
    symbol: str,
    provider: Annotated[
        TwelveDataMarketDataProvider,
        Depends(get_market_data_provider),
    ],
) -> MarketPriceResponse:
    """
    Return the latest market price for one symbol.
    """

    normalized = _normalize_symbol(symbol)

    try:
        price = provider.get_price(normalized)
    except TwelveDataRequestError as exc:
        _raise_provider_request_error(exc)
    except TwelveDataResponseError as exc:
        _raise_provider_response_error(exc)

    return MarketPriceResponse(
        symbol=normalized,
        price=price,
    )


@router.get(
    "/quote/{symbol}",
    response_model=MarketQuoteResponse,
)
def read_market_quote(
    symbol: str,
    provider: Annotated[
        TwelveDataMarketDataProvider,
        Depends(get_market_data_provider),
    ],
) -> MarketQuoteResponse:
    """
    Return the latest normalized market snapshot for one symbol.
    """

    normalized = _normalize_symbol(symbol)

    try:
        snapshot = provider.get_quote(normalized)
    except TwelveDataRequestError as exc:
        _raise_provider_request_error(exc)
    except TwelveDataResponseError as exc:
        _raise_provider_response_error(exc)

    return MarketQuoteResponse.from_snapshot(snapshot)


@router.get(
    "/quotes",
    response_model=MarketBatchQuoteResponse,
)
def read_market_quotes(
    symbols: Annotated[
        str,
        Query(
            min_length=1,
            description="Comma-separated market symbols.",
            examples=[
                "AAPL,MSFT,GOOGL,NVDA",
            ],
        ),
    ],
    provider: Annotated[
        TwelveDataMarketDataProvider,
        Depends(get_market_data_provider),
    ],
    cache: Annotated[
        MarketSnapshotCache,
        Depends(get_market_snapshot_cache),
    ],
) -> MarketBatchQuoteResponse:
    """
    Return a batch of market snapshots.

    Fresh Redis entries are resolved before upstream requests are made.
    Only cache misses are sent to Twelve Data.

    If the upstream provider fails, BatchMarketQuoteService may use stale
    Redis snapshots for affected symbols according to the configured
    cache policy.
    """

    settings = get_settings()

    normalized_symbols = _normalize_symbols(
        symbols,
        max_symbols=settings.market_batch_max_symbols,
    )

    service = BatchMarketQuoteService(
        provider=provider,
        cache=cache,
    )

    return service.get_quotes(normalized_symbols)


@router.get(
    "/candles",
    response_model=MarketCandlesResponse,
)
def read_market_candles(
    symbol: Annotated[
        str,
        Query(
            min_length=1,
            description="Market symbol.",
            examples=["AAPL"],
        ),
    ],
    provider: Annotated[
        TwelveDataMarketDataProvider,
        Depends(get_market_data_provider),
    ],
    range_value: Annotated[
        MarketCandleRange,
        Query(
            alias="range",
            description="Candlestick display range.",
        ),
    ] = "day",
) -> MarketCandlesResponse:
    """
    Return chronological OHLC candlesticks for a market symbol.

    Public chart ranges map to provider requests as follows:

    * day   -> 5-minute candles, 78 data points
    * week  -> 1-hour candles, 40 data points
    * month -> 1-day candles, 30 data points
    """

    normalized = _normalize_symbol(symbol)

    interval, outputsize = _resolve_candle_range(
        range_value
    )

    try:
        candles = provider.get_time_series(
            normalized,
            interval=interval,
            outputsize=outputsize,
        )
    except TwelveDataRequestError as exc:
        _raise_provider_request_error(exc)
    except TwelveDataResponseError as exc:
        _raise_provider_response_error(exc)

    items = [
        MarketCandleItem(
            time=candle.datetime,
            open=float(candle.open),
            high=float(candle.high),
            low=float(candle.low),
            close=float(candle.close),
        )
        for candle in candles
    ]

    return MarketCandlesResponse(
        symbol=normalized,
        range=range_value,
        interval=interval,
        items=items,
    )