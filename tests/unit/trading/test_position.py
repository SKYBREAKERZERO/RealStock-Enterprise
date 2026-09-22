from decimal import Decimal

import pytest

from libs.trading.exceptions import (
    InsufficientPositionError,
)
from libs.trading.models import Position


def test_buy_creates_position() -> None:
    position = Position(symbol="aapl")

    position.buy(
        quantity=100,
        price=Decimal("200"),
    )

    assert position.symbol == "AAPL"
    assert position.quantity == 100
    assert position.average_cost == Decimal("200")


def test_multiple_buys_update_average_cost() -> None:
    position = Position(symbol="AAPL")

    position.buy(
        quantity=100,
        price=Decimal("200"),
    )

    position.buy(
        quantity=100,
        price=Decimal("220"),
    )

    assert position.quantity == 200
    assert position.average_cost == Decimal("210")


def test_sell_reduces_position() -> None:
    position = Position(
        symbol="AAPL",
        quantity=100,
        average_cost=Decimal("200"),
    )

    position.sell(quantity=40)

    assert position.quantity == 60
    assert position.average_cost == Decimal("200")


def test_cannot_sell_more_than_position() -> None:
    position = Position(
        symbol="AAPL",
        quantity=10,
        average_cost=Decimal("200"),
    )

    with pytest.raises(
        InsufficientPositionError
    ):
        position.sell(quantity=20)

def test_position_calculates_market_value() -> None:
    position = Position(
        symbol="AAPL",
        quantity=100,
        average_cost=Decimal("200"),
    )

    assert position.market_value(
        Decimal("210")
    ) == Decimal("21000")


def test_position_calculates_unrealized_profit() -> None:
    position = Position(
        symbol="AAPL",
        quantity=100,
        average_cost=Decimal("200"),
    )

    assert position.unrealized_pnl(
        Decimal("210")
    ) == Decimal("1000")


def test_position_calculates_unrealized_loss() -> None:
    position = Position(
        symbol="AAPL",
        quantity=100,
        average_cost=Decimal("200"),
    )

    assert position.unrealized_pnl(
        Decimal("190")
    ) == Decimal("-1000")


def test_sell_calculates_realized_profit() -> None:
    position = Position(
        symbol="AAPL",
        quantity=100,
        average_cost=Decimal("200"),
    )

    position.sell(
        quantity=40,
        price=Decimal("215"),
    )

    assert position.quantity == 60
    assert position.average_cost == Decimal("200")
    assert position.realized_pnl == Decimal("600")


def test_sell_calculates_realized_loss() -> None:
    position = Position(
        symbol="AAPL",
        quantity=100,
        average_cost=Decimal("200"),
    )

    position.sell(
        quantity=20,
        price=Decimal("190"),
    )

    assert position.quantity == 80
    assert position.realized_pnl == Decimal("-200")