from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

from redis.exceptions import RedisError

from services.api.market_batch import (
    BatchMarketQuoteService,
)
from services.api.schemas.market import (
    MarketQuoteResponse,
)
from services.market_ingestor.providers.twelve_data import (
    TwelveDataBatchQuoteResult,
    TwelveDataQuoteSnapshot,
    TwelveDataRequestError,
)


def build_snapshot(
    symbol: str,
) -> TwelveDataQuoteSnapshot:
    return TwelveDataQuoteSnapshot(
        symbol=symbol,
        name=f"{symbol} Company",
        exchange="NASDAQ",
        mic_code="XNGS",
        currency="USD",
        open=Decimal(
            "100.10"
        ),
        high=Decimal(
            "102.20"
        ),
        low=Decimal(
            "99.90"
        ),
        close=Decimal(
            "101.50"
        ),
        previous_close=Decimal(
            "100.00"
        ),
        change=Decimal(
            "1.50"
        ),
        percent_change=Decimal(
            "1.50"
        ),
        volume=1000000,
        average_volume=900000,
        is_market_open=False,
        timestamp=datetime(
            2026,
            9,
            18,
            13,
            30,
            tzinfo=UTC,
        ),
        last_quote_at=datetime(
            2026,
            9,
            18,
            19,
            59,
            tzinfo=UTC,
        ),
        fifty_two_week=None,
    )


def build_quote(
    symbol: str,
) -> MarketQuoteResponse:
    return (
        MarketQuoteResponse
        .from_snapshot(
            build_snapshot(
                symbol
            )
        )
    )


class FakeProvider:
    def __init__(
        self,
        *,
        quotes: dict[
            str,
            TwelveDataQuoteSnapshot,
        ] | None = None,
        errors: dict[
            str,
            str,
        ] | None = None,
        failure: bool = False,
    ) -> None:
        self.quotes = (
            quotes
            or {}
        )

        self.errors = (
            errors
            or {}
        )

        self.failure = (
            failure
        )

        self.calls: list[
            list[str]
        ] = []

    def get_quotes(
        self,
        symbols: list[str],
    ) -> TwelveDataBatchQuoteResult:
        self.calls.append(
            list(
                symbols
            )
        )

        if self.failure:
            raise (
                TwelveDataRequestError(
                    "provider unavailable"
                )
            )

        return (
            TwelveDataBatchQuoteResult(
                quotes={
                    symbol:
                        self.quotes[
                            symbol
                        ]
                    for symbol
                    in symbols
                    if symbol
                    in self.quotes
                },
                errors={
                    symbol:
                        self.errors[
                            symbol
                        ]
                    for symbol
                    in symbols
                    if symbol
                    in self.errors
                },
            )
        )


class FakeCache:
    def __init__(
        self,
        *,
        fresh: dict[
            str,
            MarketQuoteResponse,
        ] | None = None,
        stale: dict[
            str,
            MarketQuoteResponse,
        ] | None = None,
        fail_fresh: bool = False,
        fail_stale: bool = False,
        fail_write: bool = False,
    ) -> None:
        self.fresh = (
            fresh
            or {}
        )

        self.stale = (
            stale
            or {}
        )

        self.fail_fresh = (
            fail_fresh
        )

        self.fail_stale = (
            fail_stale
        )

        self.fail_write = (
            fail_write
        )

        self.written: list[
            MarketQuoteResponse
        ] = []

    def get_fresh_many(
        self,
        symbols: list[str],
    ) -> dict[
        str,
        MarketQuoteResponse,
    ]:
        if self.fail_fresh:
            raise RedisError(
                "redis unavailable"
            )

        return {
            symbol:
                self.fresh[
                    symbol
                ]
            for symbol
            in symbols
            if symbol
            in self.fresh
        }

    def get_stale_many(
        self,
        symbols: list[str],
    ) -> dict[
        str,
        MarketQuoteResponse,
    ]:
        if self.fail_stale:
            raise RedisError(
                "redis unavailable"
            )

        return {
            symbol:
                self.stale[
                    symbol
                ]
            for symbol
            in symbols
            if symbol
            in self.stale
        }

    def put_many(
        self,
        quotes: list[
            MarketQuoteResponse
        ],
    ) -> None:
        if self.fail_write:
            raise RedisError(
                "redis unavailable"
            )

        self.written.extend(
            quotes
        )


def test_fresh_cache_hit_does_not_call_provider() -> None:
    provider = FakeProvider()

    cache = FakeCache(
        fresh={
            "AAPL": build_quote(
                "AAPL"
            ),
        }
    )

    service = (
        BatchMarketQuoteService(
            provider=provider,
            cache=cache,
        )
    )

    response = service.get_quotes(
        [
            "AAPL",
        ]
    )

    assert provider.calls == []

    assert (
        response.items[
            0
        ].source
        == "cache"
    )

    assert (
        response.items[
            0
        ].status
        == "ok"
    )


def test_only_cache_misses_are_requested_from_provider() -> None:
    provider = FakeProvider(
        quotes={
            "MSFT": build_snapshot(
                "MSFT"
            ),
        }
    )

    cache = FakeCache(
        fresh={
            "AAPL": build_quote(
                "AAPL"
            ),
        }
    )

    service = (
        BatchMarketQuoteService(
            provider=provider,
            cache=cache,
        )
    )

    response = service.get_quotes(
        [
            "AAPL",
            "MSFT",
        ]
    )

    assert provider.calls == [
        [
            "MSFT",
        ]
    ]

    assert [
        item.symbol
        for item
        in response.items
    ] == [
        "AAPL",
        "MSFT",
    ]

    assert [
        item.source
        for item
        in response.items
    ] == [
        "cache",
        "provider",
    ]


def test_provider_results_are_written_to_cache() -> None:
    provider = FakeProvider(
        quotes={
            "AAPL": build_snapshot(
                "AAPL"
            ),
        }
    )

    cache = FakeCache()

    service = (
        BatchMarketQuoteService(
            provider=provider,
            cache=cache,
        )
    )

    service.get_quotes(
        [
            "AAPL",
        ]
    )

    assert len(
        cache.written
    ) == 1

    assert (
        cache.written[
            0
        ].symbol
        == "AAPL"
    )


def test_provider_failure_uses_stale_cache() -> None:
    provider = FakeProvider(
        failure=True,
    )

    cache = FakeCache(
        stale={
            "NVDA": build_quote(
                "NVDA"
            ),
        }
    )

    service = (
        BatchMarketQuoteService(
            provider=provider,
            cache=cache,
        )
    )

    response = service.get_quotes(
        [
            "NVDA",
        ]
    )

    item = response.items[
        0
    ]

    assert (
        item.status
        == "stale"
    )

    assert (
        item.source
        == "stale_cache"
    )

    assert (
        item.quote
        is not None
    )

    assert (
        response.stale
        == 1
    )

    assert (
        response.failed
        == 0
    )


def test_provider_partial_failure_returns_partial_success() -> None:
    provider = FakeProvider(
        quotes={
            "AAPL": build_snapshot(
                "AAPL"
            ),
        },
        errors={
            "INVALID": (
                "symbol unavailable"
            ),
        },
    )

    cache = FakeCache()

    service = (
        BatchMarketQuoteService(
            provider=provider,
            cache=cache,
        )
    )

    response = service.get_quotes(
        [
            "AAPL",
            "INVALID",
        ]
    )

    assert (
        response.requested
        == 2
    )

    assert (
        response.succeeded
        == 1
    )

    assert (
        response.failed
        == 1
    )

    assert (
        response.items[
            0
        ].status
        == "ok"
    )

    assert (
        response.items[
            1
        ].status
        == "error"
    )


def test_redis_read_failure_does_not_break_provider() -> None:
    provider = FakeProvider(
        quotes={
            "AAPL": build_snapshot(
                "AAPL"
            ),
        }
    )

    cache = FakeCache(
        fail_fresh=True,
    )

    service = (
        BatchMarketQuoteService(
            provider=provider,
            cache=cache,
        )
    )

    response = service.get_quotes(
        [
            "AAPL",
        ]
    )

    assert (
        response.succeeded
        == 1
    )

    assert (
        response.items[
            0
        ].source
        == "provider"
    )


def test_redis_write_failure_does_not_break_provider_response() -> None:
    provider = FakeProvider(
        quotes={
            "AAPL": build_snapshot(
                "AAPL"
            ),
        }
    )

    cache = FakeCache(
        fail_write=True,
    )

    service = (
        BatchMarketQuoteService(
            provider=provider,
            cache=cache,
        )
    )

    response = service.get_quotes(
        [
            "AAPL",
        ]
    )

    assert (
        response.succeeded
        == 1
    )

    assert (
        response.items[
            0
        ].source
        == "provider"
    )


def test_response_preserves_requested_order() -> None:
    provider = FakeProvider(
        quotes={
            "NVDA": build_snapshot(
                "NVDA"
            ),
            "MSFT": build_snapshot(
                "MSFT"
            ),
        }
    )

    cache = FakeCache(
        fresh={
            "AAPL": build_quote(
                "AAPL"
            ),
        }
    )

    service = (
        BatchMarketQuoteService(
            provider=provider,
            cache=cache,
        )
    )

    response = service.get_quotes(
        [
            "NVDA",
            "AAPL",
            "MSFT",
        ]
    )

    assert [
        item.symbol
        for item
        in response.items
    ] == [
        "NVDA",
        "AAPL",
        "MSFT",
    ]