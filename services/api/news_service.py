from __future__ import annotations

import logging

from redis.exceptions import RedisError

from services.api.news_cache import NewsCache
from services.api.news_provider import (
    NewsProviderError,
    TwelveDataNewsProvider,
)
from services.api.schemas.news import NewsResponse

logger = logging.getLogger(
    __name__
)


class NewsService:
    """
    Application service for watchlist-driven news.

    Flow:

        watchlist symbols
              ↓
        Redis fresh cache
              ↓ miss
        Twelve Data batch request
              ↓
        Redis fresh + stale cache
              ↓ provider failure
        Redis stale fallback
    """

    _PROVIDER_FETCH_LIMIT = 20

    def __init__(
        self,
        *,
        provider:
            TwelveDataNewsProvider,
        cache:
            NewsCache,
    ) -> None:
        self._provider = provider
        self._cache = cache

    def get_latest(
        self,
        *,
        symbols: list[str],
        limit: int,
    ) -> NewsResponse:
        normalized_symbols = (
            self._normalize_symbols(
                symbols
            )
        )

        if not normalized_symbols:
            return NewsResponse(
                items=[],
                count=0,
                cached=False,
            )

        fresh = None

        try:
            fresh = (
                self._cache
                .get_fresh(
                    normalized_symbols
                )
            )

        except (
            RedisError,
            ValueError,
        ):
            logger.exception(
                "Unable to read fresh "
                "news cache"
            )

        if fresh is not None:
            items = fresh[
                :limit
            ]

            return NewsResponse(
                items=items,
                count=len(items),
                cached=True,
            )

        try:
            provider_items = (
                self._provider
                .get_latest(
                    symbols=(
                        normalized_symbols
                    ),
                    limit=(
                        self
                        ._PROVIDER_FETCH_LIMIT
                    ),
                )
            )

            try:
                self._cache.put(
                    normalized_symbols,
                    provider_items,
                )

            except RedisError:
                logger.exception(
                    "Unable to write "
                    "news cache"
                )

            items = provider_items[
                :limit
            ]

            return NewsResponse(
                items=items,
                count=len(items),
                cached=False,
            )

        except NewsProviderError:
            logger.warning(
                "Live news provider "
                "request failed",
                exc_info=True,
            )

        stale = None

        try:
            stale = (
                self._cache
                .get_stale(
                    normalized_symbols
                )
            )

        except (
            RedisError,
            ValueError,
        ):
            logger.exception(
                "Unable to read stale "
                "news cache"
            )

        if stale is not None:
            items = stale[
                :limit
            ]

            return NewsResponse(
                items=items,
                count=len(items),
                cached=True,
            )

        raise NewsProviderError(
            "Live news is currently "
            "unavailable and no cached "
            "news is available."
        )

    @staticmethod
    def _normalize_symbols(
        symbols: list[str],
    ) -> list[str]:
        result: list[str] = []

        seen: set[str] = set()

        for symbol in symbols:
            normalized = (
                symbol
                .strip()
                .upper()
            )

            if not normalized:
                continue

            if normalized in seen:
                continue

            seen.add(
                normalized
            )

            result.append(
                normalized
            )

        return result