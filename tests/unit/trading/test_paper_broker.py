from decimal import Decimal

import pytest

from libs.trading.enums import (
    OrderSide,
    OrderStatus,
    OrderType,
)
from libs.trading.exceptions import (
    InsufficientBuyingPowerError,
    InsufficientPositionError,
)
from libs.trading.market import MarketQuote
from libs.trading.models import (
    PaperAccount,
    PaperOrder,
    Position,
)
from libs.trading.paper_broker import PaperBroker


def test_market_buy_executes_at_ask() -> None:
    account = PaperAccount(
        initial_cash=Decimal("100000"),
    )

    position = Position(
        symbol="AAPL",
    )

    order = PaperOrder(
        account_id=account.account_id,
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=100,
        order_type=OrderType.MARKET,
    )

    quote = MarketQuote(
        symbol="AAPL",
        bid=Decimal("229.44"),
        ask=Decimal("229.46"),
    )

    broker = PaperBroker()

    execution = broker.execute_market_order(
        account=account,
        order=order,
        position=position,
        quote=quote,
    )

    assert execution.price == Decimal("229.46")
    assert execution.quantity == 100

    assert order.status == OrderStatus.FILLED
    assert order.filled_quantity == 100

    assert position.quantity == 100
    assert position.average_cost == Decimal("229.46")

    assert account.cash_balance == Decimal("77054.00")


def test_market_sell_executes_at_bid() -> None:
    account = PaperAccount(
        initial_cash=Decimal("100000"),
    )

    position = Position(
        symbol="AAPL",
        quantity=100,
        average_cost=Decimal("200"),
    )

    order = PaperOrder(
        account_id=account.account_id,
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=40,
        order_type=OrderType.MARKET,
    )

    quote = MarketQuote(
        symbol="AAPL",
        bid=Decimal("229.44"),
        ask=Decimal("229.46"),
    )

    broker = PaperBroker()

    execution = broker.execute_market_order(
        account=account,
        order=order,
        position=position,
        quote=quote,
    )

    assert execution.price == Decimal("229.44")
    assert execution.quantity == 40

    assert order.status == OrderStatus.FILLED

    assert position.quantity == 60
    assert position.average_cost == Decimal("200")

    assert account.cash_balance == Decimal("109177.60")


def test_market_buy_rejects_insufficient_buying_power() -> None:
    account = PaperAccount(
        initial_cash=Decimal("1000"),
    )

    position = Position(
        symbol="AAPL",
    )

    order = PaperOrder(
        account_id=account.account_id,
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=10,
        order_type=OrderType.MARKET,
    )

    quote = MarketQuote(
        symbol="AAPL",
        bid=Decimal("199.90"),
        ask=Decimal("200.00"),
    )

    broker = PaperBroker()

    with pytest.raises(
        InsufficientBuyingPowerError
    ):
        broker.execute_market_order(
            account=account,
            order=order,
            position=position,
            quote=quote,
        )


def test_market_sell_rejects_insufficient_position() -> None:
    account = PaperAccount(
        initial_cash=Decimal("100000"),
    )

    position = Position(
        symbol="AAPL",
        quantity=10,
        average_cost=Decimal("200"),
    )

    order = PaperOrder(
        account_id=account.account_id,
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=20,
        order_type=OrderType.MARKET,
    )

    quote = MarketQuote(
        symbol="AAPL",
        bid=Decimal("210"),
        ask=Decimal("210.10"),
    )

    broker = PaperBroker()

    with pytest.raises(
        InsufficientPositionError
    ):
        broker.execute_market_order(
            account=account,
            order=order,
            position=position,
            quote=quote,
        )


def test_order_and_quote_symbols_must_match() -> None:
    account = PaperAccount(
        initial_cash=Decimal("100000"),
    )

    position = Position(
        symbol="AAPL",
    )

    order = PaperOrder(
        account_id=account.account_id,
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=10,
        order_type=OrderType.MARKET,
    )

    quote = MarketQuote(
        symbol="MSFT",
        bid=Decimal("400"),
        ask=Decimal("400.10"),
    )

    broker = PaperBroker()

    with pytest.raises(
        ValueError,
        match="Order symbol does not match",
    ):
        broker.execute_market_order(
            account=account,
            order=order,
            position=position,
            quote=quote,
        )

def test_market_sell_updates_realized_pnl() -> None:
    account = PaperAccount(
        initial_cash=Decimal("100000"),
    )

    position = Position(
        symbol="AAPL",
        quantity=100,
        average_cost=Decimal("200"),
    )

    order = PaperOrder(
        account_id=account.account_id,
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=40,
        order_type=OrderType.MARKET,
    )

    quote = MarketQuote(
        symbol="AAPL",
        bid=Decimal("215"),
        ask=Decimal("215.10"),
    )

    broker = PaperBroker()

    execution = broker.execute_market_order(
        account=account,
        order=order,
        position=position,
        quote=quote,
    )

    assert execution.price == Decimal("215")
    assert execution.quantity == 40

    assert order.status == OrderStatus.FILLED
    assert order.filled_quantity == 40

    assert position.quantity == 60
    assert position.average_cost == Decimal("200")
    assert position.realized_pnl == Decimal("600")

    assert account.cash_balance == Decimal("108600")