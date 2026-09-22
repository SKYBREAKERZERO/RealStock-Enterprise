from __future__ import annotations

from typing import Any

from services.api.market_snapshot_cache import (
    MarketSnapshotCache,
)
from services.api.schemas.market import (
    MarketQuoteResponse,
)


class FakePipeline:
    def __init__(
        self,
        store: dict[str, str],
    ) -> None:
        self._store = store
        self.commands: list[
            tuple[
                str,
                str,
                int,
            ]
        ] = []

    def set(
        self,
        key: str,
        value: str,
        *,
        ex: int,
    ) -> FakePipeline:
        self.commands.append(
            (
                key,
                value,
                ex,
            )
        )

        return self

    def execute(
        self,
    ) -> list[bool]:
        results: list[bool] = []

        for (
            key,
            value,
            _ttl,
        ) in self.commands:
            self._store[key] = (
                value
            )

            results.append(
                True
            )

        return results


class FakeRedis:
    def __init__(
        self,
    ) -> None:
        self.store: dict[
            str,
            str,
        ] = {}

        self.pipeline_instance: (
            FakePipeline
            | None
        ) = None

    def mget(
        self,
        keys: list[str],
    ) -> list[str | None]:
        return [
            self.store.get(
                key
            )
            for key in keys
        ]

    def pipeline(
        self,
        *,
        transaction: bool,
    ) -> FakePipeline:
        assert (
            transaction
            is False
        )

        pipeline = FakePipeline(
            self.store
        )

        self.pipeline_instance = (
            pipeline
        )

        return pipeline


def build_quote(
    symbol: str,
) -> MarketQuoteResponse:
    return MarketQuoteResponse(
        symbol=symbol,
        name=f"{symbol} Company",
        exchange="NASDAQ",
        mic_code="XNGS",
        currency="USD",
        open="100.10",
        high="102.20",
        low="99.90",
        close="101.50",
        previous_close="100.00",
        change="1.50",
        percent_change="1.50",
        volume=1000000,
        average_volume=900000,
        is_market_open=False,
        timestamp=(
            "2026-09-18T13:30:00Z"
        ),
        last_quote_at=(
            "2026-09-18T19:59:00Z"
        ),
        fifty_two_week=None,
    )


def create_cache(
    redis: Any,
) -> MarketSnapshotCache:
    return MarketSnapshotCache(
        redis,
        fresh_ttl_seconds=60,
        stale_ttl_seconds=900,
    )


def test_put_many_writes_fresh_and_stale_entries() -> None:
    redis = FakeRedis()

    cache = create_cache(
        redis
    )

    cache.put_many(
        [
            build_quote(
                "AAPL"
            ),
            build_quote(
                "MSFT"
            ),
        ]
    )

    pipeline = (
        redis.pipeline_instance
    )

    assert pipeline is not None

    assert len(
        pipeline.commands
    ) == 4

    assert (
        "realstock:market-snapshot:"
        "v1:fresh:AAPL"
        in redis.store
    )

    assert (
        "realstock:market-snapshot:"
        "v1:stale:AAPL"
        in redis.store
    )

    assert (
        "realstock:market-snapshot:"
        "v1:fresh:MSFT"
        in redis.store
    )

    assert (
        "realstock:market-snapshot:"
        "v1:stale:MSFT"
        in redis.store
    )


def test_get_fresh_many_returns_cached_quotes() -> None:
    redis = FakeRedis()

    cache = create_cache(
        redis
    )

    cache.put_many(
        [
            build_quote(
                "AAPL"
            ),
        ]
    )

    result = (
        cache.get_fresh_many(
            [
                "AAPL",
                "MSFT",
            ]
        )
    )

    assert list(
        result
    ) == [
        "AAPL",
    ]

    assert (
        result[
            "AAPL"
        ].symbol
        == "AAPL"
    )


def test_get_stale_many_returns_stale_quotes() -> None:
    redis = FakeRedis()

    cache = create_cache(
        redis
    )

    cache.put_many(
        [
            build_quote(
                "NVDA"
            ),
        ]
    )

    result = (
        cache.get_stale_many(
            [
                "NVDA",
            ]
        )
    )

    assert (
        result[
            "NVDA"
        ].symbol
        == "NVDA"
    )


def test_invalid_cached_json_is_ignored() -> None:
    redis = FakeRedis()

    redis.store[
        (
            "realstock:"
            "market-snapshot:"
            "v1:fresh:AAPL"
        )
    ] = (
        "{not-valid-json"
    )

    cache = create_cache(
        redis
    )

    result = (
        cache.get_fresh_many(
            [
                "AAPL",
            ]
        )
    )

    assert result == {}


def test_put_many_does_nothing_for_empty_input() -> None:
    redis = FakeRedis()

    cache = create_cache(
        redis
    )

    cache.put_many(
        []
    )

    assert (
        redis.pipeline_instance
        is None
    )


def test_stale_ttl_must_exceed_fresh_ttl() -> None:
    redis = FakeRedis()

    try:
        MarketSnapshotCache(
            redis,
            fresh_ttl_seconds=60,
            stale_ttl_seconds=60,
        )

    except ValueError as exc:
        assert (
            "stale_ttl_seconds"
            in str(exc)
        )

    else:
        raise AssertionError(
            "Expected ValueError"
        )