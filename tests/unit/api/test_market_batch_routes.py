from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from services.api.main import app
from services.api.routes import (
    market as market_routes,
)
from services.market_ingestor.providers.twelve_data import (
    TwelveDataBatchQuoteResult,
    TwelveDataQuoteSnapshot,
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


class FakeProvider:
    def __init__(
        self,
    ) -> None:
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

        quotes = {
            symbol:
                build_snapshot(
                    symbol
                )
            for symbol
            in symbols
            if symbol
            != "INVALID"
        }

        errors = {}

        if (
            "INVALID"
            in symbols
        ):
            errors[
                "INVALID"
            ] = (
                "symbol unavailable"
            )

        return (
            TwelveDataBatchQuoteResult(
                quotes=quotes,
                errors=errors,
            )
        )


class FakeCache:
    def get_fresh_many(
        self,
        _symbols: list[str],
    ) -> dict:
        return {}

    def get_stale_many(
        self,
        _symbols: list[str],
    ) -> dict:
        return {}

    def put_many(
        self,
        _quotes: list,
    ) -> None:
        return None


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch,
):
    provider = FakeProvider()
    cache = FakeCache()

    app.dependency_overrides[
        market_routes
        .get_market_data_provider
    ] = (
        lambda: provider
    )

    app.dependency_overrides[
        market_routes
        .get_market_snapshot_cache
    ] = (
        lambda: cache
    )

    monkeypatch.setattr(
        market_routes,
        "get_settings",
        lambda: SimpleNamespace(
            market_batch_max_symbols=8,
        ),
    )

    try:
        yield (
            TestClient(
                app
            ),
            provider,
        )

    finally:
        app.dependency_overrides.clear()


def test_batch_route_returns_multiple_quotes(
    client,
) -> None:
    test_client, provider = (
        client
    )

    response = test_client.get(
        
            "/api/v1/market/quotes"
            "?symbols=AAPL,MSFT,NVDA"
        
    )

    assert (
        response.status_code
        == 200
    )

    payload = (
        response.json()
    )

    assert (
        payload[
            "requested"
        ]
        == 3
    )

    assert (
        payload[
            "succeeded"
        ]
        == 3
    )

    assert (
        payload[
            "failed"
        ]
        == 0
    )

    assert [
        item["symbol"]
        for item
        in payload["items"]
    ] == [
        "AAPL",
        "MSFT",
        "NVDA",
    ]

    assert provider.calls == [
        [
            "AAPL",
            "MSFT",
            "NVDA",
        ]
    ]


def test_batch_route_normalizes_and_deduplicates(
    client,
) -> None:
    test_client, provider = (
        client
    )

    response = test_client.get(
        
            "/api/v1/market/quotes"
            "?symbols=aapl,AAPL,msft"
        
    )

    assert (
        response.status_code
        == 200
    )

    assert provider.calls == [
        [
            "AAPL",
            "MSFT",
        ]
    ]


def test_batch_route_rejects_invalid_symbol(
    client,
) -> None:
    test_client, _provider = (
        client
    )

    response = test_client.get(
        
            "/api/v1/market/quotes"
            "?symbols=AAPL,%40BAD"
        
    )

    assert (
        response.status_code
        == 422
    )


def test_batch_route_rejects_too_many_symbols(
    client,
) -> None:
    test_client, _provider = (
        client
    )

    response = test_client.get(
        
            "/api/v1/market/quotes"
            "?symbols="
            "A,B,C,D,E,F,G,H,I"
        
    )

    assert (
        response.status_code
        == 422
    )

    assert (
        response.json()[
            "detail"
        ]
        == (
            "Too many symbols. "
            "Maximum is 8."
        )
    )


def test_batch_route_supports_partial_success(
    client,
) -> None:
    test_client, _provider = (
        client
    )

    response = test_client.get(
        
            "/api/v1/market/quotes"
            "?symbols=AAPL,INVALID"
        
    )

    assert (
        response.status_code
        == 200
    )

    payload = (
        response.json()
    )

    assert (
        payload[
            "requested"
        ]
        == 2
    )

    assert (
        payload[
            "succeeded"
        ]
        == 1
    )

    assert (
        payload[
            "failed"
        ]
        == 1
    )

    assert (
        payload[
            "items"
        ][0]["status"]
        == "ok"
    )

    assert (
        payload[
            "items"
        ][1]["status"]
        == "error"
    )