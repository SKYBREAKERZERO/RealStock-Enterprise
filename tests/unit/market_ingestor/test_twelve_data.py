from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest
from pydantic import SecretStr

from services.market_ingestor.providers.twelve_data import (
    FiftyTwoWeekRange,
    TwelveDataMarketDataProvider,
    TwelveDataQuoteSnapshot,
    TwelveDataRequestError,
    TwelveDataResponseError,
)

pytestmark = pytest.mark.unit


# ============================================================
# Test data
# ============================================================


def build_quote_payload() -> dict[str, object]:
    return {
        "symbol": "AAPL",
        "name": "Apple Inc.",
        "exchange": "NASDAQ",
        "mic_code": "XNGS",
        "currency": "USD",
        "datetime": "2026-09-18",
        "timestamp": 1789738200,
        "last_quote_at": 1789761540,
        "open": "337.91000",
        "high": "338.48999",
        "low": "332.53000",
        "close": "336.13000",
        "volume": "86433100",
        "previous_close": "337",
        "change": "-0.86999512",
        "percent_change": "-0.25815879",
        "average_volume": "49158440",
        "is_market_open": False,
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


# ============================================================
# Provider configuration
# ============================================================


def test_provider_accepts_string_api_key() -> None:
    provider = TwelveDataMarketDataProvider(
        api_key="test-api-key",
    )

    provider.close()


def test_provider_accepts_secret_str_api_key() -> None:
    provider = TwelveDataMarketDataProvider(
        api_key=SecretStr(
            "test-api-key"
        ),
    )

    provider.close()


@pytest.mark.parametrize(
    "api_key",
    [
        "",
        " ",
        "   ",
    ],
)
def test_provider_rejects_blank_api_key(
    api_key: str,
) -> None:
    with pytest.raises(
        ValueError,
        match="api_key must not be empty",
    ):
        TwelveDataMarketDataProvider(
            api_key=api_key,
        )


def test_provider_rejects_blank_base_url() -> None:
    with pytest.raises(
        ValueError,
        match="base_url must not be empty",
    ):
        TwelveDataMarketDataProvider(
            api_key="test-api-key",
            base_url="   ",
        )


@pytest.mark.parametrize(
    "timeout_seconds",
    [
        0,
        -1,
        -0.1,
    ],
)
def test_provider_rejects_invalid_timeout(
    timeout_seconds: float,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "timeout_seconds must be greater than zero"
        ),
    ):
        TwelveDataMarketDataProvider(
            api_key="test-api-key",
            timeout_seconds=timeout_seconds,
        )


# ============================================================
# Price
# ============================================================


def test_get_price_returns_decimal() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert (
            request.url.path
            == "/price"
        )

        return httpx.Response(
            200,
            json={
                "price": "335.59000",
            },
        )

    transport = httpx.MockTransport(
        handler
    )

    with httpx.Client(
        transport=transport,
    ) as client:
        provider = TwelveDataMarketDataProvider(
            api_key="test-api-key",
            client=client,
        )

        price = provider.get_price(
            "AAPL"
        )

    assert (
        price
        == Decimal("335.59000")
    )


def test_get_price_normalizes_symbol() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert (
            request.url.params[
                "symbol"
            ]
            == "AAPL"
        )

        return httpx.Response(
            200,
            json={
                "price": "335.59000",
            },
        )

    transport = httpx.MockTransport(
        handler
    )

    with httpx.Client(
        transport=transport,
    ) as client:
        provider = TwelveDataMarketDataProvider(
            api_key="test-api-key",
            client=client,
        )

        provider.get_price(
            "  aapl  "
        )


def test_get_price_uses_authorization_header() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert (
            request.headers[
                "Authorization"
            ]
            == "apikey test-api-key"
        )

        assert (
            "test-api-key"
            not in str(request.url)
        )

        assert (
            "apikey"
            not in request.url.params
        )

        return httpx.Response(
            200,
            json={
                "price": "335.59000",
            },
        )

    transport = httpx.MockTransport(
        handler
    )

    with httpx.Client(
        transport=transport,
    ) as client:
        provider = TwelveDataMarketDataProvider(
            api_key="test-api-key",
            client=client,
        )

        provider.get_price(
            "AAPL"
        )


@pytest.mark.parametrize(
    "symbol",
    [
        "",
        " ",
        "   ",
    ],
)
def test_get_price_rejects_blank_symbol(
    symbol: str,
) -> None:
    provider = TwelveDataMarketDataProvider(
        api_key="test-api-key",
    )

    try:
        with pytest.raises(
            ValueError,
            match="symbol must not be empty",
        ):
            provider.get_price(
                symbol
            )
    finally:
        provider.close()


# ============================================================
# Quote
# ============================================================


def test_get_quote_returns_snapshot() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        assert (
            request.url.path
            == "/quote"
        )

        assert (
            request.url.params[
                "symbol"
            ]
            == "AAPL"
        )

        return httpx.Response(
            200,
            json=build_quote_payload(),
        )

    transport = httpx.MockTransport(
        handler
    )

    with httpx.Client(
        transport=transport,
    ) as client:
        provider = TwelveDataMarketDataProvider(
            api_key="test-api-key",
            client=client,
        )

        quote = provider.get_quote(
            "  aapl "
        )

    assert isinstance(
        quote,
        TwelveDataQuoteSnapshot,
    )

    assert quote.symbol == "AAPL"
    assert quote.name == "Apple Inc."
    assert quote.exchange == "NASDAQ"
    assert quote.mic_code == "XNGS"
    assert quote.currency == "USD"

    assert (
        quote.open
        == Decimal("337.91000")
    )

    assert (
        quote.high
        == Decimal("338.48999")
    )

    assert (
        quote.low
        == Decimal("332.53000")
    )

    assert (
        quote.close
        == Decimal("336.13000")
    )

    assert (
        quote.previous_close
        == Decimal("337")
    )

    assert (
        quote.change
        == Decimal("-0.86999512")
    )

    assert (
        quote.percent_change
        == Decimal("-0.25815879")
    )

    assert quote.volume == 86433100

    assert (
        quote.average_volume
        == 49158440
    )

    assert (
        quote.is_market_open
        is False
    )

    assert quote.timestamp == datetime(
        2026,
        9,
        18,
        13,
        30,
        tzinfo=UTC,
    )

    assert (
        quote.last_quote_at
        == datetime(
            2026,
            9,
            18,
            19,
            59,
            tzinfo=UTC,
        )
    )


def test_get_quote_parses_fifty_two_week() -> None:
    def handler(
        _request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json=build_quote_payload(),
        )

    transport = httpx.MockTransport(
        handler
    )

    with httpx.Client(
        transport=transport,
    ) as client:
        provider = TwelveDataMarketDataProvider(
            api_key="test-api-key",
            client=client,
        )

        quote = provider.get_quote(
            "AAPL"
        )

    assert isinstance(
        quote.fifty_two_week,
        FiftyTwoWeekRange,
    )

    assert (
        quote.fifty_two_week.low
        == Decimal("236.64999")
    )

    assert (
        quote.fifty_two_week.high
        == Decimal("344.57001")
    )

    assert (
        quote.fifty_two_week.range
        == "236.649994 - 344.570007"
    )


def test_get_quote_allows_missing_last_quote_at() -> None:
    payload = build_quote_payload()

    payload.pop(
        "last_quote_at"
    )

    def handler(
        _request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json=payload,
        )

    transport = httpx.MockTransport(
        handler
    )

    with httpx.Client(
        transport=transport,
    ) as client:
        provider = TwelveDataMarketDataProvider(
            api_key="test-api-key",
            client=client,
        )

        quote = provider.get_quote(
            "AAPL"
        )

    assert (
        quote.last_quote_at
        is None
    )


def test_get_quote_allows_missing_fifty_two_week() -> None:
    payload = build_quote_payload()

    payload.pop(
        "fifty_two_week"
    )

    def handler(
        _request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json=payload,
        )

    transport = httpx.MockTransport(
        handler
    )

    with httpx.Client(
        transport=transport,
    ) as client:
        provider = TwelveDataMarketDataProvider(
            api_key="test-api-key",
            client=client,
        )

        quote = provider.get_quote(
            "AAPL"
        )

    assert (
        quote.fifty_two_week
        is None
    )


@pytest.mark.parametrize(
    "symbol",
    [
        "",
        " ",
        "   ",
    ],
)
def test_get_quote_rejects_blank_symbol(
    symbol: str,
) -> None:
    provider = TwelveDataMarketDataProvider(
        api_key="test-api-key",
    )

    try:
        with pytest.raises(
            ValueError,
            match="symbol must not be empty",
        ):
            provider.get_quote(
                symbol
            )
    finally:
        provider.close()


# ============================================================
# Response validation
# ============================================================


def test_api_error_response_is_rejected() -> None:
    def handler(
        _request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": "error",
                "code": 400,
                "message": (
                    "Invalid symbol"
                ),
            },
        )

    transport = httpx.MockTransport(
        handler
    )

    with httpx.Client(
        transport=transport,
    ) as client:
        provider = TwelveDataMarketDataProvider(
            api_key="test-api-key",
            client=client,
        )

        with pytest.raises(
            TwelveDataResponseError,
            match=(
                "Twelve Data API error "
                "code=400: Invalid symbol"
            ),
        ):
            provider.get_price(
                "INVALID"
            )


def test_http_error_is_wrapped() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            429,
            request=request,
            json={
                "status": "error",
            },
        )

    transport = httpx.MockTransport(
        handler
    )

    with httpx.Client(
        transport=transport,
    ) as client:
        provider = TwelveDataMarketDataProvider(
            api_key="test-api-key",
            client=client,
        )

        with pytest.raises(
            TwelveDataRequestError,
            match=(
                "Twelve Data request failed"
            ),
        ):
            provider.get_price(
                "AAPL"
            )


def test_network_error_is_wrapped() -> None:
    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        raise httpx.ConnectError(
            "connection failed",
            request=request,
        )

    transport = httpx.MockTransport(
        handler
    )

    with httpx.Client(
        transport=transport,
    ) as client:
        provider = TwelveDataMarketDataProvider(
            api_key="test-api-key",
            client=client,
        )

        with pytest.raises(
            TwelveDataRequestError,
            match=(
                "Twelve Data request failed"
            ),
        ):
            provider.get_price(
                "AAPL"
            )


def test_invalid_json_is_rejected() -> None:
    def handler(
        _request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            content=b"not-json",
            headers={
                "Content-Type": (
                    "text/plain"
                ),
            },
        )

    transport = httpx.MockTransport(
        handler
    )

    with httpx.Client(
        transport=transport,
    ) as client:
        provider = TwelveDataMarketDataProvider(
            api_key="test-api-key",
            client=client,
        )

        with pytest.raises(
            TwelveDataResponseError,
            match=(
                "Twelve Data returned invalid JSON"
            ),
        ):
            provider.get_price(
                "AAPL"
            )


def test_non_object_json_is_rejected() -> None:
    def handler(
        _request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                "unexpected",
            ],
        )

    transport = httpx.MockTransport(
        handler
    )

    with httpx.Client(
        transport=transport,
    ) as client:
        provider = TwelveDataMarketDataProvider(
            api_key="test-api-key",
            client=client,
        )

        with pytest.raises(
            TwelveDataResponseError,
            match=(
                "Twelve Data response "
                "must be a JSON object"
            ),
        ):
            provider.get_price(
                "AAPL"
            )


def test_missing_price_is_rejected() -> None:
    def handler(
        _request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={},
        )

    transport = httpx.MockTransport(
        handler
    )

    with httpx.Client(
        transport=transport,
    ) as client:
        provider = TwelveDataMarketDataProvider(
            api_key="test-api-key",
            client=client,
        )

        with pytest.raises(
            TwelveDataResponseError,
            match="Missing field: price",
        ):
            provider.get_price(
                "AAPL"
            )


def test_invalid_price_is_rejected() -> None:
    def handler(
        _request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "price": "invalid",
            },
        )

    transport = httpx.MockTransport(
        handler
    )

    with httpx.Client(
        transport=transport,
    ) as client:
        provider = TwelveDataMarketDataProvider(
            api_key="test-api-key",
            client=client,
        )

        with pytest.raises(
            TwelveDataResponseError,
            match=(
                "Invalid decimal field: price"
            ),
        ):
            provider.get_price(
                "AAPL"
            )


def test_invalid_market_open_boolean_is_rejected() -> None:
    payload = build_quote_payload()

    payload[
        "is_market_open"
    ] = "false"

    def handler(
        _request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json=payload,
        )

    transport = httpx.MockTransport(
        handler
    )

    with httpx.Client(
        transport=transport,
    ) as client:
        provider = TwelveDataMarketDataProvider(
            api_key="test-api-key",
            client=client,
        )

        with pytest.raises(
            TwelveDataResponseError,
            match=(
                "Invalid boolean field: "
                "is_market_open"
            ),
        ):
            provider.get_quote(
                "AAPL"
            )


def test_missing_required_quote_field_is_rejected() -> None:
    payload = build_quote_payload()

    payload.pop(
        "exchange"
    )

    def handler(
        _request: httpx.Request,
    ) -> httpx.Response:
        return httpx.Response(
            200,
            json=payload,
        )

    transport = httpx.MockTransport(
        handler
    )

    with httpx.Client(
        transport=transport,
    ) as client:
        provider = TwelveDataMarketDataProvider(
            api_key="test-api-key",
            client=client,
        )

        with pytest.raises(
            TwelveDataResponseError,
            match="Missing field: exchange",
        ):
            provider.get_quote(
                "AAPL"
            )