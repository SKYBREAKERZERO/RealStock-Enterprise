from __future__ import annotations

from pydantic import ValidationError
from redis import Redis

from services.api.schemas.market import (
    MarketQuoteResponse,
)


class MarketSnapshotCache:
    """
    Redis cache for Twelve Data OHLC snapshots.

    This is intentionally separate from the existing
    bid/ask MarketQuote domain cache.
    """

    KEY_PREFIX = (
        "realstock:"
        "market-snapshot:"
        "v1"
    )

    def __init__(
        self,
        redis_client: Redis,
        *,
        fresh_ttl_seconds: int,
        stale_ttl_seconds: int,
    ) -> None:
        if fresh_ttl_seconds <= 0:
            raise ValueError(
                "fresh_ttl_seconds must be greater than zero"
            )

        if (
            stale_ttl_seconds
            <= fresh_ttl_seconds
        ):
            raise ValueError(
                "stale_ttl_seconds must be greater "
                "than fresh_ttl_seconds"
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

    @classmethod
    def _fresh_key(
        cls,
        symbol: str,
    ) -> str:
        return (
            f"{cls.KEY_PREFIX}:"
            f"fresh:{symbol}"
        )

    @classmethod
    def _stale_key(
        cls,
        symbol: str,
    ) -> str:
        return (
            f"{cls.KEY_PREFIX}:"
            f"stale:{symbol}"
        )

    @staticmethod
    def _deserialize(
        raw: bytes | str | None,
    ) -> MarketQuoteResponse | None:
        if raw is None:
            return None

        try:
            return (
                MarketQuoteResponse
                .model_validate_json(
                    raw
                )
            )

        except ValidationError:
            return None

    def get_fresh_many(
        self,
        symbols: list[str],
    ) -> dict[
        str,
        MarketQuoteResponse,
    ]:
        if not symbols:
            return {}

        keys = [
            self._fresh_key(
                symbol
            )
            for symbol
            in symbols
        ]

        values = (
            self._redis.mget(
                keys
            )
        )

        result: dict[
            str,
            MarketQuoteResponse,
        ] = {}

        for symbol, raw in zip(
            symbols,
            values,
            strict=True,
        ):
            quote = (
                self._deserialize(
                    raw
                )
            )

            if quote is not None:
                result[symbol] = (
                    quote
                )

        return result

    def get_stale_many(
        self,
        symbols: list[str],
    ) -> dict[
        str,
        MarketQuoteResponse,
    ]:
        if not symbols:
            return {}

        keys = [
            self._stale_key(
                symbol
            )
            for symbol
            in symbols
        ]

        values = (
            self._redis.mget(
                keys
            )
        )

        result: dict[
            str,
            MarketQuoteResponse,
        ] = {}

        for symbol, raw in zip(
            symbols,
            values,
            strict=True,
        ):
            quote = (
                self._deserialize(
                    raw
                )
            )

            if quote is not None:
                result[symbol] = (
                    quote
                )

        return result

    def put_many(
        self,
        quotes: list[
            MarketQuoteResponse
        ],
    ) -> None:
        if not quotes:
            return

        pipeline = (
            self._redis.pipeline(
                transaction=False
            )
        )

        for quote in quotes:
            payload = (
                quote
                .model_dump_json()
            )

            pipeline.set(
                self._fresh_key(
                    quote.symbol
                ),
                payload,
                ex=(
                    self
                    ._fresh_ttl_seconds
                ),
            )

            pipeline.set(
                self._stale_key(
                    quote.symbol
                ),
                payload,
                ex=(
                    self
                    ._stale_ttl_seconds
                ),
            )

        pipeline.execute()