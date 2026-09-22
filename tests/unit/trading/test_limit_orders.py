from decimal import Decimal

from libs.trading.enums import (
    OrderSide,
    OrderStatus,
    OrderType,
)
from libs.trading.market import MarketQuote
from libs.trading.models import (
    PaperAccount,
    PaperOrder,
    Position,
)
from libs.trading.paper_broker import PaperBroker


def test_limit_buy_stays_pending_above_limit() -> None:
    account = PaperAccount(
        initial_cash=Decimal("100000"),
    )

    position = Position(symbol="AAPL")

    order = PaperOrder(
        account_id=account.account_id,
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=100,
        order_type=OrderType.LIMIT,
        limit_price=Decimal("200"),
    )

    quote = MarketQuote(
        symbol="AAPL",
        bid=Decimal("204.90"),
        ask=Decimal("205"),
    )

    broker = PaperBroker()

    broker.submit_limit_order(
        order=order,
        position=position,
        quote=quote,
    )

    execution = broker.process_quote(
        account=account,
        order=order,
        position=position,
        quote=quote,
    )

    assert execution is None
    assert order.status == OrderStatus.PENDING
    assert position.quantity == 0
    assert account.cash_balance == Decimal("100000")


def test_limit_buy_fills_when_ask_reaches_limit() -> None:
    account = PaperAccount(
        initial_cash=Decimal("100000"),
    )

    position = Position(symbol="AAPL")

    order = PaperOrder(
        account_id=account.account_id,
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=100,
        order_type=OrderType.LIMIT,
        limit_price=Decimal("200"),
    )

    broker = PaperBroker()

    broker.submit_limit_order(
        order=order,
        position=position,
        quote=MarketQuote(
            symbol="AAPL",
            bid=Decimal("204.90"),
            ask=Decimal("205"),
        ),
    )

    execution = broker.process_quote(
        account=account,
        order=order,
        position=position,
        quote=MarketQuote(
            symbol="AAPL",
            bid=Decimal("199.90"),
            ask=Decimal("199.95"),
        ),
    )

    assert execution is not None
    assert execution.price == Decimal("199.95")
    assert order.status == OrderStatus.FILLED
    assert position.quantity == 100
    assert position.average_cost == Decimal("199.95")
    assert account.cash_balance == Decimal("80005.00")


def test_limit_sell_stays_pending_below_limit() -> None:
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
        order_type=OrderType.LIMIT,
        limit_price=Decimal("220"),
    )

    quote = MarketQuote(
        symbol="AAPL",
        bid=Decimal("215"),
        ask=Decimal("215.10"),
    )

    broker = PaperBroker()

    broker.submit_limit_order(
        order=order,
        position=position,
        quote=quote,
    )

    execution = broker.process_quote(
        account=account,
        order=order,
        position=position,
        quote=quote,
    )

    assert execution is None
    assert order.status == OrderStatus.PENDING
    assert position.quantity == 100


def test_limit_sell_fills_when_bid_reaches_limit() -> None:
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
        order_type=OrderType.LIMIT,
        limit_price=Decimal("220"),
    )

    broker = PaperBroker()

    broker.submit_limit_order(
        order=order,
        position=position,
        quote=MarketQuote(
            symbol="AAPL",
            bid=Decimal("215"),
            ask=Decimal("215.10"),
        ),
    )

    execution = broker.process_quote(
        account=account,
        order=order,
        position=position,
        quote=MarketQuote(
            symbol="AAPL",
            bid=Decimal("221"),
            ask=Decimal("221.10"),
        ),
    )

    assert execution is not None
    assert execution.price == Decimal("221")
    assert order.status == OrderStatus.FILLED
    assert position.quantity == 60
    assert position.realized_pnl == Decimal("840")
    assert account.cash_balance == Decimal("108840")


def test_pending_limit_order_can_be_cancelled() -> None:
    account = PaperAccount(
        initial_cash=Decimal("100000"),
    )

    position = Position(symbol="AAPL")

    order = PaperOrder(
        account_id=account.account_id,
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=100,
        order_type=OrderType.LIMIT,
        limit_price=Decimal("200"),
    )

    quote = MarketQuote(
        symbol="AAPL",
        bid=Decimal("204.90"),
        ask=Decimal("205"),
    )

    broker = PaperBroker()

    broker.submit_limit_order(
        order=order,
        position=position,
        quote=quote,
    )

    broker.cancel_order(
        order=order,
    )

    assert order.status == OrderStatus.CANCELLED


def test_cancelled_limit_order_never_fills() -> None:
    account = PaperAccount(
        initial_cash=Decimal("100000"),
    )

    position = Position(symbol="AAPL")

    order = PaperOrder(
        account_id=account.account_id,
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=100,
        order_type=OrderType.LIMIT,
        limit_price=Decimal("200"),
    )

    broker = PaperBroker()

    broker.submit_limit_order(
        order=order,
        position=position,
        quote=MarketQuote(
            symbol="AAPL",
            bid=Decimal("205"),
            ask=Decimal("205.10"),
        ),
    )

    broker.cancel_order(
        order=order,
    )

    execution = broker.process_quote(
        account=account,
        order=order,
        position=position,
        quote=MarketQuote(
            symbol="AAPL",
            bid=Decimal("199"),
            ask=Decimal("199.10"),
        ),
    )

    assert execution is None
    assert order.status == OrderStatus.CANCELLED
    assert position.quantity == 0
    assert account.cash_balance == Decimal("100000")