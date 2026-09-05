from __future__ import annotations

from datetime import (
    datetime,
    timezone,
)
from decimal import Decimal
from unittest.mock import Mock

import pytest

from libs.cache import MarketQuoteCache
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


pytestmark = pytest.mark.unit


def build_position(
    *,
    symbol: str,
    quantity: str,
    average_cost: str,
) -> Position:
    return Position(
        symbol=symbol,
        market=Market.US,
        quantity=Decimal(quantity),
        average_cost=Decimal(average_cost),
    )


def build_quote(
    *,
    symbol: str,
    bid_price: str,
    ask_price: str,
) -> MarketQuote:
    return MarketQuote(
        symbol=symbol,
        market=Market.US,
        bid_price=Decimal(bid_price),
        ask_price=Decimal(ask_price),
        bid_size=100,
        ask_size=120,
        timestamp=datetime(
            2026,
            9,
            5,
            1,
            30,
            0,
            tzinfo=timezone.utc,
        ),
    )


def test_values_single_position() -> None:
    position = build_position(
        symbol="AAPL",
        quantity="100",
        average_cost="200.50",
    )

    portfolio = Portfolio(
        user_id="user-001",
        name="Growth Portfolio",
        positions=(
            position,
        ),
    )

    quote_cache = Mock(
        spec=MarketQuoteCache
    )

    quote_cache.get_quote.return_value = (
        build_quote(
            symbol="AAPL",
            bid_price="210",
            ask_price="212",
        )
    )

    service = PortfolioValuationService(
        quote_cache=quote_cache,
    )

    result = service.value_portfolio(
        portfolio=portfolio,
    )

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

    assert result.priced_positions == 1
    assert result.missing_quotes == 0
    assert result.valuation_complete is True


def test_reads_quote_using_position_instrument() -> None:
    position = build_position(
        symbol="AAPL",
        quantity="100",
        average_cost="200.50",
    )

    portfolio = Portfolio(
        user_id="user-001",
        name="Growth Portfolio",
        positions=(
            position,
        ),
    )

    quote_cache = Mock(
        spec=MarketQuoteCache
    )

    quote_cache.get_quote.return_value = (
        build_quote(
            symbol="AAPL",
            bid_price="210",
            ask_price="212",
        )
    )

    service = PortfolioValuationService(
        quote_cache=quote_cache,
    )

    service.value_portfolio(
        portfolio=portfolio,
    )

    quote_cache.get_quote.assert_called_once_with(
        market=Market.US,
        symbol="AAPL",
    )


def test_values_multiple_positions() -> None:
    aapl = build_position(
        symbol="AAPL",
        quantity="100",
        average_cost="200.50",
    )

    msft = build_position(
        symbol="MSFT",
        quantity="10",
        average_cost="300",
    )

    portfolio = Portfolio(
        user_id="user-001",
        name="Growth Portfolio",
        positions=(
            aapl,
            msft,
        ),
    )

    quote_cache = Mock(
        spec=MarketQuoteCache
    )

    quotes = {
        "AAPL": build_quote(
            symbol="AAPL",
            bid_price="210",
            ask_price="212",
        ),
        "MSFT": build_quote(
            symbol="MSFT",
            bid_price="320",
            ask_price="322",
        ),
    }

    quote_cache.get_quote.side_effect = (
        lambda *,
        market,
        symbol: quotes[symbol]
    )

    service = PortfolioValuationService(
        quote_cache=quote_cache,
    )

    result = service.value_portfolio(
        portfolio=portfolio,
    )

    assert result.priced_positions == 2
    assert result.missing_quotes == 0

    assert (
        result.total_cost_basis
        == Decimal("23050.00")
    )

    assert (
        result.priced_cost_basis
        == Decimal("23050.00")
    )

    assert (
        result.total_market_value
        == Decimal("24310")
    )

    assert (
        result.total_unrealized_pnl
        == Decimal("1260.00")
    )

    assert result.valuation_complete is True


def test_handles_missing_quote() -> None:
    aapl = build_position(
        symbol="AAPL",
        quantity="100",
        average_cost="200.50",
    )

    msft = build_position(
        symbol="MSFT",
        quantity="10",
        average_cost="300",
    )

    portfolio = Portfolio(
        user_id="user-001",
        name="Growth Portfolio",
        positions=(
            aapl,
            msft,
        ),
    )

    quote_cache = Mock(
        spec=MarketQuoteCache
    )

    def get_quote(
        *,
        market,
        symbol,
    ):
        if symbol == "AAPL":
            return build_quote(
                symbol="AAPL",
                bid_price="210",
                ask_price="212",
            )

        return None

    quote_cache.get_quote.side_effect = (
        get_quote
    )

    service = PortfolioValuationService(
        quote_cache=quote_cache,
    )

    result = service.value_portfolio(
        portfolio=portfolio,
    )

    assert result.priced_positions == 1
    assert result.missing_quotes == 1
    assert result.valuation_complete is False

    assert (
        result.total_cost_basis
        == Decimal("23050.00")
    )

    assert (
        result.priced_cost_basis
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

    msft_result = result.positions[1]

    assert msft_result.symbol == "MSFT"
    assert msft_result.quote_available is False
    assert msft_result.market_price is None
    assert msft_result.market_value is None


def test_empty_portfolio_returns_complete_zero_valuation() -> None:
    portfolio = Portfolio(
        user_id="user-001",
        name="Empty Portfolio",
    )

    quote_cache = Mock(
        spec=MarketQuoteCache
    )

    service = PortfolioValuationService(
        quote_cache=quote_cache,
    )

    result = service.value_portfolio(
        portfolio=portfolio,
    )

    assert (
        result.total_cost_basis
        == Decimal("0")
    )

    assert (
        result.priced_cost_basis
        == Decimal("0")
    )

    assert (
        result.total_market_value
        == Decimal("0")
    )

    assert (
        result.total_unrealized_pnl
        == Decimal("0")
    )

    assert result.priced_positions == 0
    assert result.missing_quotes == 0
    assert result.valuation_complete is True
    assert result.positions == ()

    quote_cache.get_quote.assert_not_called()