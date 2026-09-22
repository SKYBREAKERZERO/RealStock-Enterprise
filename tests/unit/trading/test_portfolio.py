from decimal import Decimal

import pytest
from libs.trading.portfolio import PortfolioCalculator

from libs.trading.models import PaperAccount, Position


def test_portfolio_calculates_equity() -> None:
    account = PaperAccount(
        initial_cash=Decimal("100000"),
        cash_balance=Decimal("80000"),
    )

    position = Position(
        symbol="AAPL",
        quantity=100,
        average_cost=Decimal("200"),
    )

    calculator = PortfolioCalculator()

    snapshot = calculator.calculate(
        account=account,
        positions=[position],
        market_prices={
            "AAPL": Decimal("210"),
        },
    )

    assert snapshot.cash_balance == Decimal("80000")
    assert snapshot.market_value == Decimal("21000")
    assert snapshot.equity == Decimal("101000")
    assert snapshot.unrealized_pnl == Decimal("1000")


def test_portfolio_supports_multiple_positions() -> None:
    account = PaperAccount(
        initial_cash=Decimal("100000"),
        cash_balance=Decimal("50000"),
    )

    positions = [
        Position(
            symbol="AAPL",
            quantity=100,
            average_cost=Decimal("200"),
        ),
        Position(
            symbol="MSFT",
            quantity=50,
            average_cost=Decimal("400"),
        ),
    ]

    calculator = PortfolioCalculator()

    snapshot = calculator.calculate(
        account=account,
        positions=positions,
        market_prices={
            "AAPL": Decimal("210"),
            "MSFT": Decimal("410"),
        },
    )

    assert snapshot.market_value == Decimal("41500")
    assert snapshot.equity == Decimal("91500")
    assert snapshot.unrealized_pnl == Decimal("1500")


def test_portfolio_includes_realized_pnl() -> None:
    account = PaperAccount(
        initial_cash=Decimal("100000"),
    )

    position = Position(
        symbol="AAPL",
        quantity=100,
        average_cost=Decimal("200"),
    )

    position.sell(
        quantity=40,
        price=Decimal("215"),
    )

    calculator = PortfolioCalculator()

    snapshot = calculator.calculate(
        account=account,
        positions=[position],
        market_prices={
            "AAPL": Decimal("210"),
        },
    )

    assert snapshot.realized_pnl == Decimal("600")
    assert snapshot.unrealized_pnl == Decimal("600")


def test_portfolio_requires_price_for_open_position() -> None:
    account = PaperAccount(
        initial_cash=Decimal("100000"),
    )

    position = Position(
        symbol="AAPL",
        quantity=100,
        average_cost=Decimal("200"),
    )

    calculator = PortfolioCalculator()

    with pytest.raises(
        ValueError,
        match="Missing market price for AAPL",
    ):
        calculator.calculate(
            account=account,
            positions=[position],
            market_prices={},
        )