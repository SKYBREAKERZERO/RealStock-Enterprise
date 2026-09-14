from __future__ import annotations

from datetime import (
    UTC,
    datetime,
)
from decimal import Decimal

import pytest

from libs.domain.market import (
    Market,
    MarketQuote,
)
from libs.domain.portfolio import (
    Portfolio,
    Position,
)
from libs.domain.valuation import (
    PortfolioValuation,
    PositionValuation,
)

pytestmark = pytest.mark.unit


def build_position(
    *,
    symbol: str = "AAPL",
    quantity: Decimal = Decimal("100"),
    average_cost: Decimal = Decimal("200.50"),
) -> Position:
    return Position(
        symbol=symbol,
        market=Market.US,
        quantity=quantity,
        average_cost=average_cost,
    )


def build_quote(
    *,
    symbol: str = "AAPL",
    bid_price: Decimal = Decimal("210"),
    ask_price: Decimal = Decimal("212"),
) -> MarketQuote:
    return MarketQuote(
        symbol=symbol,
        market=Market.US,
        bid_price=bid_price,
        ask_price=ask_price,
        bid_size=100,
        ask_size=120,
        timestamp=datetime(
            2026,
            9,
            5,
            1,
            0,
            0,
            tzinfo=UTC,
        ),
    )


def test_position_valuation_uses_mid_price() -> None:
    position = build_position()

    valuation = PositionValuation.from_position(
        position=position,
        quote=build_quote(),
    )

    assert (
        valuation.market_price
        == Decimal("211")
    )


def test_position_valuation_calculates_market_value() -> None:
    position = build_position()

    valuation = PositionValuation.from_position(
        position=position,
        quote=build_quote(),
    )

    assert (
        valuation.cost_basis
        == Decimal("20050.00")
    )

    assert (
        valuation.market_value
        == Decimal("21100")
    )


def test_position_valuation_calculates_unrealized_pnl() -> None:
    valuation = PositionValuation.from_position(
        position=build_position(),
        quote=build_quote(),
    )

    assert (
        valuation.unrealized_pnl
        == Decimal("1050.00")
    )


def test_position_valuation_calculates_pnl_percent() -> None:
    valuation = PositionValuation.from_position(
        position=build_position(),
        quote=build_quote(),
    )

    expected = (
        Decimal("1050.00")
        / Decimal("20050.00")
        * Decimal("100")
    )

    assert (
        valuation.unrealized_pnl_percent
        == expected
    )


def test_missing_quote_is_explicit() -> None:
    valuation = PositionValuation.from_position(
        position=build_position(),
        quote=None,
    )

    assert valuation.quote_available is False
    assert valuation.market_price is None
    assert valuation.market_value is None
    assert valuation.unrealized_pnl is None
    assert valuation.unrealized_pnl_percent is None
    assert valuation.quote_timestamp is None


def test_quote_instrument_must_match_position() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "quote instrument does not "
            "match position"
        ),
    ):
        PositionValuation.from_position(
            position=build_position(
                symbol="AAPL"
            ),
            quote=build_quote(
                symbol="MSFT"
            ),
        )


def test_portfolio_valuation_all_quotes_available() -> None:
    position = build_position()

    portfolio = Portfolio(
        user_id="user-001",
        name="Growth Portfolio",
        positions=(
            position,
        ),
    )

    position_valuation = (
        PositionValuation.from_position(
            position=position,
            quote=build_quote(),
        )
    )

    valuation = (
        PortfolioValuation.from_positions(
            portfolio=portfolio,
            positions=(
                position_valuation,
            ),
        )
    )

    assert (
        valuation.total_cost_basis
        == Decimal("20050.00")
    )

    assert (
        valuation.priced_cost_basis
        == Decimal("20050.00")
    )

    assert (
        valuation.total_market_value
        == Decimal("21100")
    )

    assert (
        valuation.total_unrealized_pnl
        == Decimal("1050.00")
    )

    assert valuation.priced_positions == 1
    assert valuation.missing_quotes == 0
    assert valuation.valuation_complete is True


def test_portfolio_valuation_handles_missing_quote() -> None:
    aapl = build_position(
        symbol="AAPL",
        quantity=Decimal("100"),
        average_cost=Decimal("200.50"),
    )

    msft = build_position(
        symbol="MSFT",
        quantity=Decimal("10"),
        average_cost=Decimal("300"),
    )

    portfolio = Portfolio(
        user_id="user-001",
        name="Growth Portfolio",
        positions=(
            aapl,
            msft,
        ),
    )

    aapl_valuation = (
        PositionValuation.from_position(
            position=aapl,
            quote=build_quote(
                symbol="AAPL"
            ),
        )
    )

    msft_valuation = (
        PositionValuation.from_position(
            position=msft,
            quote=None,
        )
    )

    valuation = (
        PortfolioValuation.from_positions(
            portfolio=portfolio,
            positions=(
                aapl_valuation,
                msft_valuation,
            ),
        )
    )

    assert (
        valuation.total_cost_basis
        == Decimal("23050.00")
    )

    assert (
        valuation.priced_cost_basis
        == Decimal("20050.00")
    )

    assert (
        valuation.total_market_value
        == Decimal("21100")
    )

    assert (
        valuation.total_unrealized_pnl
        == Decimal("1050.00")
    )

    assert valuation.priced_positions == 1
    assert valuation.missing_quotes == 1
    assert valuation.valuation_complete is False