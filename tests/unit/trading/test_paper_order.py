from uuid import uuid4

import pytest

from libs.trading.enums import (
    OrderSide,
    OrderStatus,
    OrderType,
)
from libs.trading.models import PaperOrder


def test_market_order_can_be_created() -> None:
    order = PaperOrder(
        account_id=uuid4(),
        symbol="aapl",
        side=OrderSide.BUY,
        quantity=100,
        order_type=OrderType.MARKET,
    )

    assert order.symbol == "AAPL"
    assert order.status == OrderStatus.NEW
    assert order.remaining_quantity == 100


def test_limit_order_requires_limit_price() -> None:
    with pytest.raises(ValueError):
        PaperOrder(
            account_id=uuid4(),
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.LIMIT,
        )


def test_order_supports_partial_fill() -> None:
    order = PaperOrder(
        account_id=uuid4(),
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=100,
        order_type=OrderType.MARKET,
    )

    order.mark_pending()
    order.record_fill(40)

    assert order.status == OrderStatus.PARTIALLY_FILLED
    assert order.filled_quantity == 40
    assert order.remaining_quantity == 60

    order.record_fill(60)

    assert order.status == OrderStatus.FILLED
    assert order.filled_quantity == 100