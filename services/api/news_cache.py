from __future__ import annotations

import hashlib

from pydantic import TypeAdapter
from redis import Redis

from services.api.schemas.news import NewsItem

_NEWS_ITEMS_ADAPTER = TypeAdapter(
    list[NewsItem]
)


class NewsCache:
    """
    Redis fresh/stale cache for watchlist news.

    Cache identity is derived from the normalized
    symbol set rather than user identity because
    market news is public data.
    """

    _PREFIX = (
        "realstock:news:v1"
    )

    def __init__(
        self,
        redis_client: Redis,
        *,
        fresh_ttl_seconds: int,
        stale_ttl_seconds: int,
    ) -> None:
        if (
            fresh_ttl_seconds
            <= 0
        ):
            raise ValueError(
                "fresh_ttl_seconds "
                "must be positive"
            )

        if (
            stale_ttl_seconds
            <= fresh_ttl_seconds
        ):
            raise ValueError(
                "stale_ttl_seconds "
                "must be greater than "
                "fresh_ttl_seconds"
            )

        self._redis = (
            redis_client
        )

        self._fresh_ttl_seconds = (
            fresh_ttl_seconds
        )

        self._stale_ttl_seconds = (
            stale_ttl_seconds
        )

    def get_fresh(
        self,
        symbols: list[str],
    ) -> list[NewsItem] | None:
        return self._read(
            self._fresh_key(
                symbols
            )
        )

    def get_stale(
        self,
        symbols: list[str],
    ) -> list[NewsItem] | None:
        return self._read(
            self._stale_key(
                symbols
            )
        )

    def put(
        self,
        symbols: list[str],
        items: list[NewsItem],
    ) -> None:
        payload = (
            _NEWS_ITEMS_ADAPTER
            .dump_json(
                items
            )
        )

        pipeline = (
            self._redis.pipeline(
                transaction=False,
            )
        )

        pipeline.setex(
            self._fresh_key(
                symbols
            ),
            self._fresh_ttl_seconds,
            payload,
        )

        pipeline.setex(
            self._stale_key(
                symbols
            ),
            self._stale_ttl_seconds,
            payload,
        )

        pipeline.execute()

    def _read(
        self,
        key: str,
    ) -> list[NewsItem] | None:
        raw = self._redis.get(
            key
        )

        if raw is None:
            return None

        return (
            _NEWS_ITEMS_ADAPTER
            .validate_json(
                raw
            )
        )

    @classmethod
    def _fresh_key(
        cls,
        symbols: list[str],
    ) -> str:
        return (
            f"{cls._PREFIX}:"
            f"{cls._signature(symbols)}:"
            "fresh"
        )

    @classmethod
    def _stale_key(
        cls,
        symbols: list[str],
    ) -> str:
        return (
            f"{cls._PREFIX}:"
            f"{cls._signature(symbols)}:"
            "stale"
        )

    @staticmethod
    def _signature(
        symbols: list[str],
    ) -> str:
        normalized = sorted({
            symbol
            .strip()
            .upper()
            for symbol in symbols
            if symbol.strip()
        })

        canonical = (
            ",".join(
                normalized
            )
        )

        return hashlib.sha256(
            canonical.encode(
                "utf-8"
            )
        ).hexdigest()[
            :24
        ]