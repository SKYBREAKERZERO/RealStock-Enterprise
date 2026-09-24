from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock

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
    Position,
)
from libs.trading.paper_broker import PaperBroker
from services.trading.paper_trading_service import (
    PaperTradingService,
)
from services.trading.persistent_paper_trading_service import (
    PersistentPaperTradingService,
)
from services.trading.quote_service import QuoteService


class StubQuoteProvider:
    def __init__(
        self,
        quote: MarketQuote,
    ) -> None:
        self.quote = quote

    def get_quote(
        self,
        symbol: str,
    ) -> MarketQuote:
        return self.quote


def build_trading_service(
    *,
    bid: str = "210",
    ask: str = "212",
) -> PaperTradingService:
    provider = StubQuoteProvider(
        MarketQuote(
            symbol="AAPL",
            bid=Decimal(bid),
            ask=Decimal(ask),
        )
    )

    return PaperTradingService(
        quote_service=QuoteService(
            provider=provider,
        ),
        broker=PaperBroker(),
    )


def build_uow(
    *,
    account: PaperAccount | None,
    position: Position | None = None,
) -> Mock:
    uow = Mock()

    uow.__enter__ = Mock(
        return_value=uow
    )

    uow.__exit__ = Mock(
        return_value=None
    )

    uow.paper_accounts.get_for_update.return_value = (
        account
    )

    uow.paper_positions.get_for_update.return_value = (
        position
    )

    uow.paper_accounts.get.side_effect = AssertionError(
        "Trading path must not use unlocked account reads."
    )

    uow.paper_positions.get.side_effect = AssertionError(
        "Trading path must not use unlocked position reads."
    )

    return uow


def test_market_buy_persists_complete_trade() -> None:
    account = PaperAccount(
        initial_cash=Decimal("100000"),
    )

    uow = build_uow(
        account=account,
    )

    service = PersistentPaperTradingService(
        trading_service=build_trading_service(),
        unit_of_work=uow,
    )

    result = service.market_buy(
        account_id=account.account_id,
        symbol="AAPL",
        quantity=10,
    )

    assert result.order.status == OrderStatus.FILLED
    assert result.order.filled_quantity == 10

    assert (
        result.execution.order_id
        == result.order.order_id
    )

    assert (
        result.execution.price
        == Decimal("212")
    )

    assert result.execution.quantity == 10

    assert (
        account.cash_balance
        == Decimal("97880")
    )

    uow.paper_accounts.get_for_update.assert_called_once_with(
        account.account_id
    )

    uow.paper_positions.get_for_update.assert_called_once_with(
        account_id=account.account_id,
        symbol="AAPL",
    )

    uow.paper_accounts.get.assert_not_called()
    uow.paper_positions.get.assert_not_called()

    uow.paper_accounts.update.assert_called_once_with(
        account
    )

    uow.paper_positions.upsert.assert_called_once()

    upsert_kwargs = (
        uow.paper_positions
        .upsert
        .call_args
        .kwargs
    )

    assert (
        upsert_kwargs["account_id"]
        == account.account_id
    )

    persisted_position = (
        upsert_kwargs["position"]
    )

    assert persisted_position.symbol == "AAPL"
    assert persisted_position.quantity == 10

    assert (
        persisted_position.average_cost
        == Decimal("212")
    )

    uow.paper_orders.add.assert_called_once_with(
        result.order
    )

    uow.paper_executions.add.assert_called_once_with(
        account_id=account.account_id,
        execution=result.execution,
    )

    uow.commit.assert_called_once_with()


def test_market_buy_updates_existing_position() -> None:
    account = PaperAccount(
        initial_cash=Decimal("100000"),
    )

    position = Position(
        symbol="AAPL",
        quantity=5,
        average_cost=Decimal("200"),
    )

    uow = build_uow(
        account=account,
        position=position,
    )

    service = PersistentPaperTradingService(
        trading_service=build_trading_service(),
        unit_of_work=uow,
    )

    result = service.market_buy(
        account_id=account.account_id,
        symbol="aapl",
        quantity=5,
    )

    assert result.order.status == OrderStatus.FILLED
    assert position.quantity == 10

    assert (
        position.average_cost
        == Decimal("206")
    )

    assert (
        account.cash_balance
        == Decimal("98940")
    )

    uow.paper_accounts.get_for_update.assert_called_once_with(
        account.account_id
    )

    uow.paper_positions.get_for_update.assert_called_once_with(
        account_id=account.account_id,
        symbol="AAPL",
    )

    uow.paper_accounts.get.assert_not_called()
    uow.paper_positions.get.assert_not_called()

    uow.paper_positions.upsert.assert_called_once_with(
        account_id=account.account_id,
        position=position,
    )

    uow.commit.assert_called_once_with()


def test_market_sell_persists_complete_trade() -> None:
    account = PaperAccount(
        initial_cash=Decimal("100000"),
    )

    position = Position(
        symbol="AAPL",
        quantity=20,
        average_cost=Decimal("200"),
    )

    uow = build_uow(
        account=account,
        position=position,
    )

    service = PersistentPaperTradingService(
        trading_service=build_trading_service(
            bid="210",
            ask="212",
        ),
        unit_of_work=uow,
    )

    result = service.market_sell(
        account_id=account.account_id,
        symbol="AAPL",
        quantity=10,
    )

    assert result.order.status == OrderStatus.FILLED
    assert result.order.filled_quantity == 10

    assert (
        result.execution.price
        == Decimal("210")
    )

    assert result.execution.quantity == 10
    assert position.quantity == 10

    assert (
        position.realized_pnl
        == Decimal("100")
    )

    assert (
        account.cash_balance
        == Decimal("102100")
    )

    uow.paper_accounts.get_for_update.assert_called_once_with(
        account.account_id
    )

    uow.paper_positions.get_for_update.assert_called_once_with(
        account_id=account.account_id,
        symbol="AAPL",
    )

    uow.paper_accounts.get.assert_not_called()
    uow.paper_positions.get.assert_not_called()

    uow.paper_accounts.update.assert_called_once_with(
        account
    )

    uow.paper_positions.upsert.assert_called_once_with(
        account_id=account.account_id,
        position=position,
    )

    uow.paper_orders.add.assert_called_once_with(
        result.order
    )

    uow.paper_executions.add.assert_called_once_with(
        account_id=account.account_id,
        execution=result.execution,
    )

    uow.commit.assert_called_once_with()


def test_missing_account_does_not_commit() -> None:
    account = PaperAccount(
        initial_cash=Decimal("100000"),
    )

    uow = build_uow(
        account=None,
    )

    service = PersistentPaperTradingService(
        trading_service=build_trading_service(),
        unit_of_work=uow,
    )

    with pytest.raises(
        ValueError,
        match="Paper account .* not found",
    ):
        service.market_buy(
            account_id=account.account_id,
            symbol="AAPL",
            quantity=10,
        )

    uow.paper_accounts.get_for_update.assert_called_once_with(
        account.account_id
    )

    uow.paper_positions.get_for_update.assert_not_called()

    uow.paper_accounts.get.assert_not_called()
    uow.paper_positions.get.assert_not_called()

    uow.paper_accounts.update.assert_not_called()
    uow.paper_positions.upsert.assert_not_called()
    uow.paper_orders.add.assert_not_called()
    uow.paper_executions.add.assert_not_called()

    uow.commit.assert_not_called()


def test_failed_trade_does_not_persist_or_commit() -> None:
    account = PaperAccount(
        initial_cash=Decimal("100"),
    )

    uow = build_uow(
        account=account,
    )

    service = PersistentPaperTradingService(
        trading_service=build_trading_service(),
        unit_of_work=uow,
    )

    with pytest.raises(
        InsufficientBuyingPowerError,
    ):
        service.market_buy(
            account_id=account.account_id,
            symbol="AAPL",
            quantity=10,
        )

    assert (
        account.cash_balance
        == Decimal("100")
    )

    uow.paper_accounts.get_for_update.assert_called_once_with(
        account.account_id
    )

    uow.paper_positions.get_for_update.assert_called_once_with(
        account_id=account.account_id,
        symbol="AAPL",
    )

    uow.paper_accounts.get.assert_not_called()
    uow.paper_positions.get.assert_not_called()

    uow.paper_accounts.update.assert_not_called()
    uow.paper_positions.upsert.assert_not_called()
    uow.paper_orders.add.assert_not_called()
    uow.paper_executions.add.assert_not_called()

    uow.commit.assert_not_called()


def test_market_sell_without_position_does_not_commit() -> None:
    account = PaperAccount(
        initial_cash=Decimal("100000"),
    )

    uow = build_uow(
        account=account,
        position=None,
    )

    service = PersistentPaperTradingService(
        trading_service=build_trading_service(),
        unit_of_work=uow,
    )

    with pytest.raises(
        InsufficientPositionError,
    ):
        service.market_sell(
            account_id=account.account_id,
            symbol="AAPL",
            quantity=10,
        )

    assert (
        account.cash_balance
        == Decimal("100000")
    )

    uow.paper_accounts.get_for_update.assert_called_once_with(
        account.account_id
    )

    uow.paper_positions.get_for_update.assert_called_once_with(
        account_id=account.account_id,
        symbol="AAPL",
    )

    uow.paper_accounts.get.assert_not_called()
    uow.paper_positions.get.assert_not_called()

    uow.paper_accounts.update.assert_not_called()
    uow.paper_positions.upsert.assert_not_called()
    uow.paper_orders.add.assert_not_called()
    uow.paper_executions.add.assert_not_called()

    uow.commit.assert_not_called()


def test_empty_symbol_fails_before_unit_of_work() -> None:
    account = PaperAccount(
        initial_cash=Decimal("100000"),
    )

    uow = build_uow(
        account=account,
    )

    service = PersistentPaperTradingService(
        trading_service=build_trading_service(),
        unit_of_work=uow,
    )

    with pytest.raises(
        ValueError,
        match="Symbol must not be empty",
    ):
        service.market_buy(
            account_id=account.account_id,
            symbol="   ",
            quantity=10,
        )

    uow.__enter__.assert_not_called()

    uow.paper_accounts.get_for_update.assert_not_called()
    uow.paper_positions.get_for_update.assert_not_called()

    uow.paper_accounts.get.assert_not_called()
    uow.paper_positions.get.assert_not_called()

    uow.commit.assert_not_called()


def test_submit_limit_buy_persists_pending_order_only() -> None:
    account = PaperAccount(
        initial_cash=Decimal("100000"),
    )

    uow = build_uow(
        account=account,
    )

    service = PersistentPaperTradingService(
        trading_service=build_trading_service(),
        unit_of_work=uow,
    )

    order = service.submit_limit_buy(
        account_id=account.account_id,
        symbol="aapl",
        quantity=10,
        limit_price=Decimal("200"),
    )

    assert order.account_id == account.account_id
    assert order.symbol == "AAPL"
    assert order.side == OrderSide.BUY
    assert order.order_type == OrderType.LIMIT
    assert order.status == OrderStatus.PENDING
    assert order.quantity == 10
    assert order.filled_quantity == 0

    assert (
        order.limit_price
        == Decimal("200")
    )

    assert (
        account.cash_balance
        == Decimal("100000")
    )

    uow.paper_accounts.get_for_update.assert_called_once_with(
        account.account_id
    )

    uow.paper_positions.get_for_update.assert_called_once_with(
        account_id=account.account_id,
        symbol="AAPL",
    )

    uow.paper_accounts.get.assert_not_called()
    uow.paper_positions.get.assert_not_called()

    uow.paper_accounts.update.assert_not_called()
    uow.paper_positions.upsert.assert_not_called()

    uow.paper_orders.add.assert_called_once_with(
        order
    )

    uow.paper_executions.add.assert_not_called()

    uow.commit.assert_called_once_with()


def test_submit_limit_sell_persists_pending_order_only() -> None:
    account = PaperAccount(
        initial_cash=Decimal("100000"),
    )

    uow = build_uow(
        account=account,
    )

    service = PersistentPaperTradingService(
        trading_service=build_trading_service(),
        unit_of_work=uow,
    )

    order = service.submit_limit_sell(
        account_id=account.account_id,
        symbol="aapl",
        quantity=10,
        limit_price=Decimal("220"),
    )

    assert order.account_id == account.account_id
    assert order.symbol == "AAPL"
    assert order.side == OrderSide.SELL
    assert order.order_type == OrderType.LIMIT
    assert order.status == OrderStatus.PENDING
    assert order.quantity == 10
    assert order.filled_quantity == 0

    assert (
        order.limit_price
        == Decimal("220")
    )

    assert (
        account.cash_balance
        == Decimal("100000")
    )

    uow.paper_accounts.get_for_update.assert_called_once_with(
        account.account_id
    )

    uow.paper_positions.get_for_update.assert_called_once_with(
        account_id=account.account_id,
        symbol="AAPL",
    )

    uow.paper_accounts.get.assert_not_called()
    uow.paper_positions.get.assert_not_called()

    uow.paper_accounts.update.assert_not_called()
    uow.paper_positions.upsert.assert_not_called()

    uow.paper_orders.add.assert_called_once_with(
        order
    )

    uow.paper_executions.add.assert_not_called()

    uow.commit.assert_called_once_with()