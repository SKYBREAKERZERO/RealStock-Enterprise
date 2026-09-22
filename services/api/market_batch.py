from __future__ import annotations

import logging

from redis.exceptions import RedisError

from services.api.market_snapshot_cache import (
    MarketSnapshotCache,
)
from services.api.schemas.market import (
    MarketBatchQuoteItem,
    MarketBatchQuoteResponse,
    MarketQuoteResponse,
)
from services.market_ingestor.providers.twelve_data import (
    TwelveDataError,
    TwelveDataMarketDataProvider,
)

logger = logging.getLogger(
    __name__
)


class BatchMarketQuoteService:
    """
    Batch market quote application service.

    Flow:

        requested symbols
              ↓
        Redis fresh cache
              ↓ misses only
        Twelve Data batch request
              ↓
        Redis fresh + stale cache
              ↓
        partial-success response

    Redis is treated as an optimization layer rather than
    a mandatory dependency of market-data availability.
    """

    def __init__(
        self,
        *,
        provider:
            TwelveDataMarketDataProvider,
        cache:
            MarketSnapshotCache,
    ) -> None:
        self._provider = provider
        self._cache = cache

    def get_quotes(
        self,
        symbols: list[str],
    ) -> MarketBatchQuoteResponse:
        fresh_quotes: dict[
            str,
            MarketQuoteResponse,
        ] = {}

        try:
            fresh_quotes = (
                self._cache
                .get_fresh_many(
                    symbols
                )
            )

        except RedisError:
            logger.exception(
                "Unable to read fresh market cache"
            )

        missing_symbols = [
            symbol
            for symbol
            in symbols
            if symbol
            not in fresh_quotes
        ]

        provider_quotes: dict[
            str,
            MarketQuoteResponse,
        ] = {}

        provider_errors: set[
            str
        ] = set()

        if missing_symbols:
            try:
                batch_result = (
                    self._provider
                    .get_quotes(
                        missing_symbols
                    )
                )

                provider_errors.update(
                    batch_result
                    .errors
                    .keys()
                )

                for (
                    symbol,
                    snapshot,
                ) in (
                    batch_result
                    .quotes
                    .items()
                ):
                    provider_quotes[
                        symbol
                    ] = (
                        MarketQuoteResponse
                        .from_snapshot(
                            snapshot
                        )
                    )

                if provider_quotes:
                    try:
                        self._cache.put_many(
                            list(
                                provider_quotes
                                .values()
                            )
                        )

                    except RedisError:
                        logger.exception(
                            "Unable to write market snapshot cache"
                        )

            except TwelveDataError:
                logger.warning(
                    "Twelve Data batch request failed",
                    exc_info=True,
                )

                provider_errors.update(
                    missing_symbols
                )

        unresolved_symbols = [
            symbol
            for symbol
            in missing_symbols
            if symbol
            not in provider_quotes
        ]

        stale_quotes: dict[
            str,
            MarketQuoteResponse,
        ] = {}

        if unresolved_symbols:
            try:
                stale_quotes = (
                    self._cache
                    .get_stale_many(
                        unresolved_symbols
                    )
                )

            except RedisError:
                logger.exception(
                    "Unable to read stale market cache"
                )

        items: list[
            MarketBatchQuoteItem
        ] = []

        for symbol in symbols:
            fresh = (
                fresh_quotes.get(
                    symbol
                )
            )

            if fresh is not None:
                items.append(
                    MarketBatchQuoteItem(
                        symbol=symbol,
                        status="ok",
                        source="cache",
                        quote=fresh,
                    )
                )

                continue

            provider_quote = (
                provider_quotes.get(
                    symbol
                )
            )

            if provider_quote is not None:
                items.append(
                    MarketBatchQuoteItem(
                        symbol=symbol,
                        status="ok",
                        source="provider",
                        quote=(
                            provider_quote
                        ),
                    )
                )

                continue

            stale = (
                stale_quotes.get(
                    symbol
                )
            )

            if stale is not None:
                items.append(
                    MarketBatchQuoteItem(
                        symbol=symbol,
                        status="stale",
                        source=(
                            "stale_cache"
                        ),
                        quote=stale,
                        error=(
                            "Live market data is temporarily unavailable. "
                            "Returning the last cached snapshot."
                        ),
                    )
                )

                continue

            error_message = (
                "Market data is currently "
                "unavailable for this symbol."
            )

            if symbol in provider_errors:
                error_message = (
                    "The upstream market provider "
                    "could not return this symbol."
                )

            items.append(
                MarketBatchQuoteItem(
                    symbol=symbol,
                    status="error",
                    error=(
                        error_message
                    ),
                )
            )

        succeeded = sum(
            item.status == "ok"
            for item in items
        )

        stale_count = sum(
            item.status == "stale"
            for item in items
        )

        failed = sum(
            item.status == "error"
            for item in items
        )

        return (
            MarketBatchQuoteResponse(
                requested=(
                    len(symbols)
                ),
                succeeded=(
                    succeeded
                ),
                stale=(
                    stale_count
                ),
                failed=(
                    failed
                ),
                items=items,
            )
        )