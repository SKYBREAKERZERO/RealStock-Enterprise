from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from services.api.main import app
from services.api.routes.market import get_market_data_provider
from services.market_ingestor.providers.twelve_data import (
    FiftyTwoWeekRange,
    TwelveDataQuoteSnapshot,
    TwelveDataRequestError,
    TwelveDataResponseError,
)

pytestmark = pytest.mark.unit


client = TestClient(app)


# ============================================================
# Test doubles
# ============================================================


class FakeMarketDataProvider:
    def get_price(
        self,
        symbol: str,
    ) -> Decimal:
        assert symbol == "AAPL"

        return Decimal("335.59000")

    def get_quote(
        self,
        symbol: str,
    ) -> TwelveDataQuoteSnapshot:
        assert symbol == "AAPL"

        return TwelveDataQuoteSnapshot(
            symbol="AAPL",
            name="Apple Inc.",
            exchange="NASDAQ",
            mic_code="XNGS",
            currency="USD",
            open=Decimal("337.91000"),
            high=Decimal("338.48999"),
            low=Decimal("332.53000"),
            close=Decimal("336.13000"),
            previous_close=Decimal("337"),
            change=Decimal("-0.86999512"),
            percent_change=Decimal("-0.25815879"),
            volume=86433100,
            average_volume=49158440,
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
            fifty_two_week=FiftyTwoWeekRange(
                low=Decimal("236.64999"),
                high=Decimal("344.57001"),
                low_change=Decimal("99.48001"),
                high_change=Decimal("-8.44000"),
                low_change_percent=Decimal("42.036769"),
                high_change_percent=Decimal("-2.44943"),
                range="236.649994 - 344.570007",
            ),
        )


class RequestFailureProvider:
    def get_price(
        self,
        _symbol: str,
    ) -> Decimal:
        raise TwelveDataRequestError(
            "upstream request failed"
        )

    def get_quote(
        self,
        _symbol: str,
    ) -> TwelveDataQuoteSnapshot:
        raise TwelveDataRequestError(
            "upstream request failed"
        )


class ResponseFailureProvider:
    def get_price(
        self,
        _symbol: str,
    ) -> Decimal:
        raise TwelveDataResponseError(
            "invalid upstream response"
        )

    def get_quote(
        self,
        _symbol: str,
    ) -> TwelveDataQuoteSnapshot:
        raise TwelveDataResponseError(
            "invalid upstream response"
        )


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture(autouse=True)
def reset_dependency_overrides():
    app.dependency_overrides.clear()

    yield

    app.dependency_overrides.clear()


def use_provider(
    provider: object,
) -> None:
    app.dependency_overrides[
        get_market_data_provider
    ] = lambda: provider


# ============================================================
# Price endpoint
# ============================================================


def test_get_market_price() -> None:
    use_provider(
        FakeMarketDataProvider()
    )

    response = client.get(
        "/api/v1/market/price/AAPL"
    )

    assert response.status_code == 200

    assert response.json() == {
        "symbol": "AAPL",
        "price": "335.59000",
    }


def test_market_price_normalizes_symbol() -> None:
    use_provider(
        FakeMarketDataProvider()
    )

    response = client.get(
        "/api/v1/market/price/aapl"
    )

    assert response.status_code == 200

    assert response.json()["symbol"] == "AAPL"


def test_market_price_request_failure_returns_502() -> None:
    use_provider(
        RequestFailureProvider()
    )

    response = client.get(
        "/api/v1/market/price/AAPL"
    )

    assert response.status_code == 502

    assert response.json() == {
        "detail": (
            "market data provider "
            "request failed"
        )
    }


def test_market_price_response_failure_returns_502() -> None:
    use_provider(
        ResponseFailureProvider()
    )

    response = client.get(
        "/api/v1/market/price/AAPL"
    )

    assert response.status_code == 502

    assert response.json() == {
        "detail": (
            "market data provider "
            "response failed"
        )
    }


# ============================================================
# Quote endpoint
# ============================================================


def test_get_market_quote() -> None:
    use_provider(
        FakeMarketDataProvider()
    )

    response = client.get(
        "/api/v1/market/quote/AAPL"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["symbol"] == "AAPL"
    assert payload["name"] == "Apple Inc."
    assert payload["exchange"] == "NASDAQ"
    assert payload["mic_code"] == "XNGS"
    assert payload["currency"] == "USD"

    assert payload["open"] == "337.91000"
    assert payload["high"] == "338.48999"
    assert payload["low"] == "332.53000"
    assert payload["close"] == "336.13000"

    assert payload["previous_close"] == "337"

    assert payload["change"] == "-0.86999512"

    assert (
        payload["percent_change"]
        == "-0.25815879"
    )

    assert payload["volume"] == 86433100
    assert payload["average_volume"] == 49158440

    assert payload["is_market_open"] is False

    assert (
        payload["timestamp"]
        == "2026-09-18T13:30:00Z"
    )

    assert (
        payload["last_quote_at"]
        == "2026-09-18T19:59:00Z"
    )


def test_market_quote_contains_fifty_two_week() -> None:
    use_provider(
        FakeMarketDataProvider()
    )

    response = client.get(
        "/api/v1/market/quote/AAPL"
    )

    assert response.status_code == 200

    fifty_two_week = response.json()[
        "fifty_two_week"
    ]

    assert (
        fifty_two_week["low"]
        == "236.64999"
    )

    assert (
        fifty_two_week["high"]
        == "344.57001"
    )

    assert (
        fifty_two_week["range"]
        == "236.649994 - 344.570007"
    )


def test_market_quote_request_failure_returns_502() -> None:
    use_provider(
        RequestFailureProvider()
    )

    response = client.get(
        "/api/v1/market/quote/AAPL"
    )

    assert response.status_code == 502

    assert response.json() == {
        "detail": (
            "market data provider "
            "request failed"
        )
    }


def test_market_quote_response_failure_returns_502() -> None:
    use_provider(
        ResponseFailureProvider()
    )

    response = client.get(
        "/api/v1/market/quote/AAPL"
    )

    assert response.status_code == 502

    assert response.json() == {
        "detail": (
            "market data provider "
            "response failed"
        )
    }