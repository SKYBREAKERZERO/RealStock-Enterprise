from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from typing import Any

import httpx
import pytest

from services.market_ingestor.providers.twelve_data import (
    TwelveDataMarketDataProvider,
    TwelveDataResponseError,
)

pytestmark = pytest.mark.unit


def _quote_payload() -> dict[str, Any]:
    return {
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "exchange": "NASDAQ",
        "mic_code": "XNGS",
        "currency": "USD",
        "open": "337.91000",
        "high": "338.48999",
        "low": "332.53000",
        "close": "336.13000",
        "previous_close": "337",
        "change": "-0.86999512",
        "percent_change": "-0.25815879",
        "volume": "86433100",
        "average_volume": "49158440",
        "is_market_open": False,
        "timestamp": "1789747800",
        "last_quote_at": "1789774740",
        "fifty_two_week": {
            "low": "236.64999",
            "high": "344.57001",
            "low_change": "99.48001",
            "high_change": "-8.44000",
            "low_change_percent": "42.036769",
            "high_change_percent": "-2.44943",
            "range": "236.649994 - 344.570007",
        },
    }


def _provider(
    handler: Callable[
        [httpx.Request],
        httpx.Response,
    ],
) -> tuple[
    TwelveDataMarketDataProvider,
    httpx.Client,
]:
    client = httpx.Client(
        transport=httpx.MockTransport(handler)
    )

    provider = TwelveDataMarketDataProvider(
        api_key="test-key",
        client=client,
    )

    return provider, client


def test_quote_accepts_json_false_boolean() -> None:
    payload = _quote_payload()

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json=payload,
            request=request,
        )

    provider, client = _provider(handler)

    try:
        quote = provider.get_quote("aapl")
    finally:
        client.close()

    assert quote.is_market_open is False


@pytest.mark.parametrize(
    "invalid_value",
    [
        "false",
        "true",
        0,
        1,
        None,
    ],
)
def test_quote_rejects_non_boolean_market_open(
    invalid_value: object,
) -> None:
    payload = _quote_payload()
    payload["is_market_open"] = invalid_value

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json=payload,
            request=request,
        )

    provider, client = _provider(handler)

    try:
        with pytest.raises(
            TwelveDataResponseError,
            match=(
                "Invalid boolean field: "
                "is_market_open"
            ),
        ):
            provider.get_quote("AAPL")
    finally:
        client.close()


@pytest.mark.parametrize(
    "invalid_value",
    [
        "NaN",
        "Infinity",
        "-Infinity",
    ],
)
def test_quote_rejects_non_finite_decimal(
    invalid_value: str,
) -> None:
    payload = _quote_payload()
    payload["close"] = invalid_value

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json=payload,
            request=request,
        )

    provider, client = _provider(handler)

    try:
        with pytest.raises(
            TwelveDataResponseError,
            match="Invalid decimal field: close",
        ):
            provider.get_quote("AAPL")
    finally:
        client.close()


def test_quote_rejects_non_string_required_field() -> None:
    payload = _quote_payload()
    payload["name"] = 123

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json=payload,
            request=request,
        )

    provider, client = _provider(handler)

    try:
        with pytest.raises(
            TwelveDataResponseError,
            match="Invalid string field: name",
        ):
            provider.get_quote("AAPL")
    finally:
        client.close()


def test_quote_rejects_invalid_fifty_two_week_type() -> None:
    payload = _quote_payload()
    payload["fifty_two_week"] = []

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json=payload,
            request=request,
        )

    provider, client = _provider(handler)

    try:
        with pytest.raises(
            TwelveDataResponseError,
            match="Invalid field: fifty_two_week",
        ):
            provider.get_quote("AAPL")
    finally:
        client.close()


def test_quote_rejects_symbol_mismatch() -> None:
    payload = _quote_payload()
    payload["symbol"] = "MSFT"

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json=payload,
            request=request,
        )

    provider, client = _provider(handler)

    try:
        with pytest.raises(
            TwelveDataResponseError,
            match=(
                "quote symbol does not match "
                "requested symbol"
            ),
        ):
            provider.get_quote("AAPL")
    finally:
        client.close()


def test_batch_symbol_mismatch_is_partial_error() -> None:
    aapl = _quote_payload()

    msft = deepcopy(aapl)
    msft["symbol"] = "GOOGL"
    msft["name"] = "Wrong Symbol"

    payload = {
        "AAPL": aapl,
        "MSFT": msft,
    }

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json=payload,
            request=request,
        )

    provider, client = _provider(handler)

    try:
        result = provider.get_quotes(
            ["AAPL", "MSFT"]
        )
    finally:
        client.close()

    assert list(result.quotes) == ["AAPL"]
    assert result.errors == {
        "MSFT": "Invalid market data response."
    }


def test_time_series_rejects_invalid_ohlc() -> None:
    payload = {
        "values": [
            {
                "datetime": "2026-09-18 13:30:00",
                "open": "101",
                "high": "100",
                "low": "99",
                "close": "100",
            }
        ]
    }

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json=payload,
            request=request,
        )

    provider, client = _provider(handler)

    try:
        with pytest.raises(
            TwelveDataResponseError,
            match=(
                "open is outside high/low range"
            ),
        ):
            provider.get_time_series(
                "AAPL",
                interval="5min",
                outputsize=1,
            )
    finally:
        client.close()
