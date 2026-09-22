from __future__ import annotations

from collections.abc import Generator
from datetime import (
    UTC,
    datetime,
)
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from libs.cache import (
    MarketQuoteCache,
    get_redis_client,
)
from libs.database import get_session_factory
from libs.database.models import (
    PortfolioModel,
    PositionModel,
)
from libs.domain.market import (
    Market,
    MarketQuote,
)
from services.api.dependencies import (
    get_portfolio_valuation_service,
)
from services.api.main import app
from services.api.portfolio.valuation import (
    PortfolioValuationService,
)

pytestmark = pytest.mark.integration


client = TestClient(app)


USER_HEADERS = {
    "X-User-Id": "api-user-001",
}

OTHER_USER_HEADERS = {
    "X-User-Id": "api-user-002",
}


def _get_legacy_portfolio_valuation_service(
) -> PortfolioValuationService:
    """
    Deterministic valuation dependency used by this legacy API
    integration test suite.

    These tests intentionally exercise:

        MarketQuoteCache
            -> bid / ask MarketQuote
            -> midpoint valuation

    Production runtime may instead use the configured Twelve Data
    snapshot valuation-price source.
    """

    return PortfolioValuationService()


@pytest.fixture(
    autouse=True,
)
def cleanup_and_use_legacy_valuation(
) -> Generator[
    None,
    None,
    None,
]:
    """
    Isolate portfolio valuation API tests from the real Twelve Data
    runtime and clean persistent state before and after every test.
    """

    app.dependency_overrides[
        get_portfolio_valuation_service
    ] = (
        _get_legacy_portfolio_valuation_service
    )

    session_factory = (
        get_session_factory()
    )

    redis_client = (
        get_redis_client()
    )

    with session_factory() as session:
        session.execute(
            delete(
                PositionModel
            )
        )
        session.execute(
            delete(
                PortfolioModel
            )
        )
        session.commit()

    for key in redis_client.scan_iter(
        match="realstock:quote:*"
    ):
        redis_client.delete(
            key
        )

    try:
        yield

    finally:
        with session_factory() as session:
            session.execute(
                delete(
                    PositionModel
                )
            )
            session.execute(
                delete(
                    PortfolioModel
                )
            )
            session.commit()

        for key in redis_client.scan_iter(
            match="realstock:quote:*"
        ):
            redis_client.delete(
                key
            )

        app.dependency_overrides.pop(
            get_portfolio_valuation_service,
            None,
        )


def create_portfolio_with_aapl(
) -> dict:
    portfolio_response = (
        client.post(
            "/api/v1/portfolios",
            headers=USER_HEADERS,
            json={
                "name": (
                    "Growth Portfolio"
                ),
                "currency": "USD",
            },
        )
    )

    assert (
        portfolio_response.status_code
        == 201
    )

    portfolio = (
        portfolio_response.json()
    )

    position_response = (
        client.post(
            (
                "/api/v1/portfolios/"
                f"{portfolio['portfolio_id']}"
                "/positions"
            ),
            headers=USER_HEADERS,
            json={
                "symbol": "AAPL",
                "market": "US",
                "quantity": "100",
                "average_cost": (
                    "200.50"
                ),
            },
        )
    )

    assert (
        position_response.status_code
        == 201
    )

    return portfolio


def cache_aapl_quote(
) -> None:
    cache = (
        MarketQuoteCache()
    )

    cache.set_quote(
        MarketQuote(
            symbol="AAPL",
            market=Market.US,
            bid_price=(
                Decimal("210")
            ),
            ask_price=(
                Decimal("212")
            ),
            bid_size=100,
            ask_size=120,
            timestamp=datetime(
                2026,
                9,
                5,
                2,
                0,
                0,
                tzinfo=UTC,
            ),
        )
    )


def test_get_portfolio_valuation(
) -> None:
    portfolio = (
        create_portfolio_with_aapl()
    )

    cache_aapl_quote()

    response = client.get(
        (
            "/api/v1/portfolios/"
            f"{portfolio['portfolio_id']}"
            "/valuation"
        ),
        headers=USER_HEADERS,
    )

    assert (
        response.status_code
        == 200
    )

    payload = response.json()

    assert (
        payload["portfolio_id"]
        == portfolio["portfolio_id"]
    )

    assert (
        Decimal(
            payload[
                "total_cost_basis"
            ]
        )
        == Decimal("20050.00")
    )

    assert (
        Decimal(
            payload[
                "priced_cost_basis"
            ]
        )
        == Decimal("20050.00")
    )

    assert (
        Decimal(
            payload[
                "total_market_value"
            ]
        )
        == Decimal("21100")
    )

    assert (
        Decimal(
            payload[
                "total_unrealized_pnl"
            ]
        )
        == Decimal("1050.00")
    )

    assert (
        payload["priced_positions"]
        == 1
    )

    assert (
        payload["missing_quotes"]
        == 0
    )

    assert (
        payload["valuation_complete"]
        is True
    )

    position = (
        payload["positions"][0]
    )

    assert (
        position["symbol"]
        == "AAPL"
    )

    assert (
        Decimal(
            position[
                "market_price"
            ]
        )
        == Decimal("211")
    )

    assert (
        Decimal(
            position[
                "market_value"
            ]
        )
        == Decimal("21100")
    )

    assert (
        Decimal(
            position[
                "unrealized_pnl"
            ]
        )
        == Decimal("1050.00")
    )

    assert (
        position["quote_available"]
        is True
    )


def test_missing_quote_is_explicit(
) -> None:
    portfolio = (
        create_portfolio_with_aapl()
    )

    response = client.get(
        (
            "/api/v1/portfolios/"
            f"{portfolio['portfolio_id']}"
            "/valuation"
        ),
        headers=USER_HEADERS,
    )

    assert (
        response.status_code
        == 200
    )

    payload = response.json()

    assert (
        payload["priced_positions"]
        == 0
    )

    assert (
        payload["missing_quotes"]
        == 1
    )

    assert (
        payload["valuation_complete"]
        is False
    )

    position = (
        payload["positions"][0]
    )

    assert (
        position["quote_available"]
        is False
    )

    assert (
        position["market_price"]
        is None
    )

    assert (
        position["market_value"]
        is None
    )

    assert (
        position["unrealized_pnl"]
        is None
    )


def test_other_user_cannot_get_valuation(
) -> None:
    portfolio = (
        create_portfolio_with_aapl()
    )

    cache_aapl_quote()

    response = client.get(
        (
            "/api/v1/portfolios/"
            f"{portfolio['portfolio_id']}"
            "/valuation"
        ),
        headers=(
            OTHER_USER_HEADERS
        ),
    )

    assert (
        response.status_code
        == 404
    )


def test_missing_user_header_returns_401(
) -> None:
    portfolio = (
        create_portfolio_with_aapl()
    )

    response = client.get(
        
            "/api/v1/portfolios/"
            f"{portfolio['portfolio_id']}"
            "/valuation"
        
    )

    assert (
        response.status_code
        == 401
    )