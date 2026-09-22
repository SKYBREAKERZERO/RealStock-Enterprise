from __future__ import annotations

from urllib.parse import parse_qs

import httpx
import pytest

from services.market_ingestor.providers.twelve_data import (
    TwelveDataMarketDataProvider,
)


def build_quote_payload(
    symbol: str,
) -> dict[str, object]:
    return {
        "symbol": symbol,
        "name": f"{symbol} Company",
        "exchange": "NASDAQ",
        "mic_code": "XNGS",
        "currency": "USD",
        "open": "100.10",
        "high": "102.20",
        "low": "99.90",
        "close": "101.50",
        "previous_close": "100.00",
        "change": "1.50",
        "percent_change": "1.50",
        "volume": "1000000",
        "average_volume": "900000",
        "is_market_open": False,
        "timestamp": 1789738200,
        "last_quote_at": 1789761540,
        "fifty_two_week": {
            "low": "80.00",
            "high": "120.00",
            "low_change": "21.50",
            "high_change": "-18.50",
            "low_change_percent": "26.875",
            "high_change_percent": "-15.4167",
            "range": "80.00 - 120.00",
        },
    }


def test_get_quotes_uses_one_batch_request() -> None:
    requests: list[httpx.Request] = []

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        requests.append(
            request
        )

        return httpx.Response(
            200,
            json={
                "AAPL": build_quote_payload(
                    "AAPL"
                ),
                "MSFT": build_quote_payload(
                    "MSFT"
                ),
            },
        )

    transport = httpx.MockTransport(
        handler
    )

    with httpx.Client(
        transport=transport,
    ) as client:
        provider = (
            TwelveDataMarketDataProvider(
                api_key="test-api-key",
                client=client,
            )
        )

        result = provider.get_quotes(
            [
                "AAPL",
                "MSFT",
            ]
        )

    assert len(requests) == 1

    request = requests[0]

    assert (
        request.url.path
        == "/quote"
    )

    query = parse_qs(
        request.url.query.decode()
    )

    assert query["symbol"] == [
        "AAPL,MSFT"
    ]

    assert (
        request.headers[
            "Authorization"
        ]
        == "apikey test-api-key"
    )

    assert (
        "test-api-key"
        not in str(
            request.url
        )
    )

    assert set(
        result.quotes
    ) == {
        "AAPL",
        "MSFT",
    }

    assert result.errors == {}


def test_get_quotes_normalizes_and_deduplicates_symbols() -> None:
    requested_symbol = ""

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        nonlocal requested_symbol

        query = parse_qs(
            request.url.query.decode()
        )

        requested_symbol = (
            query["symbol"][0]
        )

        return httpx.Response(
            200,
            json={
                "AAPL": build_quote_payload(
                    "AAPL"
                ),
                "MSFT": build_quote_payload(
                    "MSFT"
                ),
            },
        )

    transport = httpx.MockTransport(
        handler
    )

    with httpx.Client(
        transport=transport,
    ) as client:
        provider = (
            TwelveDataMarketDataProvider(
                api_key="test-api-key",
                client=client,
            )
        )

        result = provider.get_quotes(
            [
                " aapl ",
                "AAPL",
                " msft ",
            ]
        )

    assert (
        requested_symbol
        == "AAPL,MSFT"
    )

    assert list(
        result.quotes
    ) == [
        "AAPL",
        "MSFT",
    ]


def test_get_quotes_supports_partial_success() -> None:
    def handler(
        _request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "AAPL": build_quote_payload(
                    "AAPL"
                ),
                "INVALID": {
                    "status": "error",
                    "code": 404,
                    "message": (
                        "Symbol not found"
                    ),
                },
            },
        )

    transport = httpx.MockTransport(
        handler
    )

    with httpx.Client(
        transport=transport,
    ) as client:
        provider = (
            TwelveDataMarketDataProvider(
                api_key="test-api-key",
                client=client,
            )
        )

        result = provider.get_quotes(
            [
                "AAPL",
                "INVALID",
            ]
        )

    assert (
        result.quotes[
            "AAPL"
        ].symbol
        == "AAPL"
    )

    assert (
        "INVALID"
        in result.errors
    )


def test_get_quotes_supports_single_symbol_response() -> None:
    def handler(
        _request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json=(
                build_quote_payload(
                    "NVDA"
                )
            ),
        )

    transport = httpx.MockTransport(
        handler
    )

    with httpx.Client(
        transport=transport,
    ) as client:
        provider = (
            TwelveDataMarketDataProvider(
                api_key="test-api-key",
                client=client,
            )
        )

        result = provider.get_quotes(
            [
                "NVDA",
            ]
        )

    assert (
        result.quotes[
            "NVDA"
        ].symbol
        == "NVDA"
    )

    assert result.errors == {}


def test_get_quotes_rejects_empty_collection() -> None:
    provider = (
        TwelveDataMarketDataProvider(
            api_key="test-api-key",
        )
    )

    try:
        with pytest.raises(
            ValueError,
            match=(
                "symbols must not be empty"
            ),
        ):
            provider.get_quotes(
                []
            )

    finally:
        provider.close()


def test_get_quotes_rejects_blank_symbol() -> None:
    provider = (
        TwelveDataMarketDataProvider(
            api_key="test-api-key",
        )
    )

    try:
        with pytest.raises(
            ValueError,
            match=(
                "symbols must not contain "
                "empty values"
            ),
        ):
            provider.get_quotes(
                [
                    "AAPL",
                    " ",
                ]
            )

    finally:
        provider.close()