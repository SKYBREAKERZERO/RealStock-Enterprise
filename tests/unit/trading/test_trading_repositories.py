from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock
from uuid import uuid4

from libs.database.models import (
    PaperAccountModel,
    PaperExecutionModel,
    PaperOrderModel,
    PaperPositionModel,
)
from libs.database.repositories.trading import (
    PaperAccountRepository,
    PaperExecutionRepository,
    PaperOrderRepository,
    PaperPositionRepository,
)
from libs.trading.enums import (
    OrderSide,
    OrderStatus,
    OrderType,
)
from libs.trading.execution import Execution
from libs.trading.models import (
    PaperAccount,
    PaperOrder,
)


def test_account_repository_adds_model() -> None:
    session = Mock()

    repository = PaperAccountRepository(
        session
    )

    account = PaperAccount(
        initial_cash=Decimal("100000"),
    )

    repository.add(
        user_id="user-001",
        account=account,
    )

    model = session.add.call_args.args[0]

    assert isinstance(
        model,
        PaperAccountModel,
    )

    assert model.id == account.account_id
    assert model.user_id == "user-001"
    assert model.initial_cash == Decimal("100000")
    assert model.cash_balance == Decimal("100000")


def test_account_repository_get_for_update_uses_row_lock() -> None:
    session = Mock()

    account_id = uuid4()

    model = PaperAccountModel(
        id=account_id,
        user_id="user-001",
        initial_cash=Decimal("100000"),
        cash_balance=Decimal("90000"),
    )

    session.scalar.return_value = model

    repository = PaperAccountRepository(
        session
    )

    account = repository.get_for_update(
        account_id
    )

    assert account is not None
    assert account.account_id == account_id
    assert account.initial_cash == Decimal("100000")
    assert account.cash_balance == Decimal("90000")

    statement = session.scalar.call_args.args[0]

    assert statement._for_update_arg is not None


def test_position_repository_get_for_update_uses_row_lock() -> None:
    session = Mock()

    account_id = uuid4()

    model = PaperPositionModel(
        account_id=account_id,
        symbol="AAPL",
        quantity=10,
        average_cost=Decimal("200"),
        realized_pnl=Decimal("25"),
    )

    session.scalar.return_value = model

    repository = PaperPositionRepository(
        session
    )

    position = repository.get_for_update(
        account_id=account_id,
        symbol="aapl",
    )

    assert position is not None
    assert position.symbol == "AAPL"
    assert position.quantity == 10
    assert position.average_cost == Decimal("200")
    assert position.realized_pnl == Decimal("25")

    statement = session.scalar.call_args.args[0]

    assert statement._for_update_arg is not None


def test_order_repository_adds_model() -> None:
    session = Mock()

    repository = PaperOrderRepository(
        session
    )

    account = PaperAccount(
        initial_cash=Decimal("100000"),
    )

    order = PaperOrder(
        account_id=account.account_id,
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=10,
        order_type=OrderType.LIMIT,
        limit_price=Decimal("200"),
    )

    order.mark_pending()

    repository.add(
        order
    )

    model = session.add.call_args.args[0]

    assert isinstance(
        model,
        PaperOrderModel,
    )

    assert model.id == order.order_id
    assert model.account_id == account.account_id
    assert model.symbol == "AAPL"
    assert model.side == "BUY"
    assert model.order_type == "LIMIT"
    assert model.status == "PENDING"
    assert model.quantity == 10
    assert model.filled_quantity == 0
    assert model.limit_price == Decimal("200")

    session.flush.assert_called_once_with()


def test_order_repository_maps_model_to_domain() -> None:
    session = Mock()

    account = PaperAccount(
        initial_cash=Decimal("100000"),
    )

    source_order = PaperOrder(
        account_id=account.account_id,
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=20,
        order_type=OrderType.MARKET,
    )

    model = PaperOrderModel(
        id=source_order.order_id,
        account_id=account.account_id,
        symbol="AAPL",
        side="SELL",
        order_type="MARKET",
        status="FILLED",
        quantity=20,
        filled_quantity=20,
        limit_price=None,
    )

    session.get.return_value = model

    repository = PaperOrderRepository(
        session
    )

    order = repository.get(
        source_order.order_id
    )

    assert order is not None
    assert order.order_id == source_order.order_id
    assert order.account_id == account.account_id
    assert order.symbol == "AAPL"
    assert order.side == OrderSide.SELL
    assert order.order_type == OrderType.MARKET
    assert order.status == OrderStatus.FILLED
    assert order.quantity == 20
    assert order.filled_quantity == 20
    assert order.limit_price is None


def test_execution_repository_adds_model() -> None:
    session = Mock()

    repository = PaperExecutionRepository(
        session
    )

    account = PaperAccount(
        initial_cash=Decimal("100000"),
    )

    order = PaperOrder(
        account_id=account.account_id,
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=10,
        order_type=OrderType.MARKET,
    )

    execution = Execution(
        order_id=order.order_id,
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=10,
        price=Decimal("212"),
    )

    repository.add(
        account_id=account.account_id,
        execution=execution,
    )

    model = session.add.call_args.args[0]

    assert isinstance(
        model,
        PaperExecutionModel,
    )

    assert model.id == execution.execution_id
    assert model.order_id == order.order_id
    assert model.account_id == account.account_id
    assert model.symbol == "AAPL"
    assert model.side == "BUY"
    assert model.quantity == 10
    assert model.price == Decimal("212")