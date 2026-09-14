from __future__ import annotations

from datetime import (
    UTC,
    datetime,
)
from decimal import Decimal

import pytest

from libs.cache import (
    MarketQuoteCache,
    get_redis_client,
)
from libs.domain.market import (
    Market,
    MarketQuote,
)
from libs.domain.portfolio import (
    Portfolio,
    Position,
)
from services.api.portfolio import (
    PortfolioValuationService,
)

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def cleanup_quotes():
    redis_client = get_redis_client()

    for key in redis_client.scan_iter(
        match="realstock:quote:*"
    ):
        redis_client.delete(key)

    yield

    for key in redis_client.scan_iter(
        match="realstock:quote:*"
    ):
        redis_client.delete(key)


def build_portfolio() -> Portfolio:
    return Portfolio(
        user_id="user-001",
        name="Growth Portfolio",
        positions=(
            Position(
                symbol="AAPL",
                market=Market.US,
                quantity=Decimal("100"),
                average_cost=Decimal("200.50"),
            ),
        ),
    )


def build_quote() -> MarketQuote:
    return MarketQuote(
        symbol="AAPL",
        market=Market.US,
        bid_price=Decimal("210"),
        ask_price=Decimal("212"),
        bid_size=100,
        ask_size=120,
        timestamp=datetime(
            2026,
            9,
            5,
            3,
            0,
            0,
            tzinfo=UTC,
        ),
    )


def test_service_reads_quote_from_real_redis() -> None:
    cache = MarketQuoteCache()

    cache.set_quote(
        build_quote()
    )

    service = PortfolioValuationService(
        quote_cache=cache,
    )

    result = service.value_portfolio(
        portfolio=build_portfolio(),
    )

    assert result.priced_positions == 1
    assert result.missing_quotes == 0
    assert result.valuation_complete is True

    assert (
        result.total_cost_basis
        == Decimal("20050.00")
    )

    assert (
        result.total_market_value
        == Decimal("21100")
    )

    assert (
        result.total_unrealized_pnl
        == Decimal("1050.00")
    )


def test_service_handles_missing_quote_from_real_redis() -> None:
    cache = MarketQuoteCache()

    service = PortfolioValuationService(
        quote_cache=cache,
    )

    result = service.value_portfolio(
        portfolio=build_portfolio(),
    )

    assert result.priced_positions == 0
    assert result.missing_quotes == 1
    assert result.valuation_complete is False

    position = result.positions[0]

    assert position.quote_available is False
    assert position.market_price is None
    assert position.market_value is None
    assert position.unrealized_pnl is None