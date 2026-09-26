from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock
from uuid import uuid4

import pytest

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


def test_account_repository_get_by_user_id_maps_domain() -> None:
    session = Mock()

    account_id = uuid4()

    model = PaperAccountModel(
        id=account_id,
        user_id="user-001",
        initial_cash=Decimal("100000"),
        cash_balance=Decimal("97500"),
    )

    session.scalar.return_value = model

    repository = PaperAccountRepository(
        session
    )

    account = repository.get_by_user_id(
        "  user-001  "
    )

    assert account is not None
    assert account.account_id == account_id
    assert account.initial_cash == Decimal("100000")
    assert account.cash_balance == Decimal("97500")

    statement = session.scalar.call_args.args[0]

    compiled = statement.compile()

    assert (
        "user-001"
        in compiled.params.values()
    )


def test_account_repository_rejects_empty_user_id() -> None:
    session = Mock()

    repository = PaperAccountRepository(
        session
    )

    with pytest.raises(
        ValueError,
        match="User ID must not be empty",
    ):
        repository.get_by_user_id(
            "   "
        )

    session.scalar.assert_not_called()


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


def test_position_repository_lists_account_positions() -> None:
    session = Mock()

    account_id = uuid4()

    models = [
        PaperPositionModel(
            account_id=account_id,
            symbol="AAPL",
            quantity=10,
            average_cost=Decimal("200"),
            realized_pnl=Decimal("25"),
        ),
        PaperPositionModel(
            account_id=account_id,
            symbol="MSFT",
            quantity=5,
            average_cost=Decimal("410"),
            realized_pnl=Decimal("-10"),
        ),
    ]

    session.scalars.return_value.all.return_value = models

    repository = PaperPositionRepository(
        session
    )

    positions = repository.list_by_account(
        account_id
    )

    assert len(positions) == 2

    assert positions[0].symbol == "AAPL"
    assert positions[0].quantity == 10
    assert positions[0].average_cost == Decimal("200")
    assert positions[0].realized_pnl == Decimal("25")

    assert positions[1].symbol == "MSFT"
    assert positions[1].quantity == 5
    assert positions[1].average_cost == Decimal("410")
    assert positions[1].realized_pnl == Decimal("-10")

    statement = session.scalars.call_args.args[0]

    assert "ORDER BY paper_positions.symbol ASC" in str(
        statement
    )


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


def test_order_repository_lists_account_orders() -> None:
    session = Mock()

    account_id = uuid4()

    first_id = uuid4()
    second_id = uuid4()

    models = [
        PaperOrderModel(
            id=first_id,
            account_id=account_id,
            symbol="MSFT",
            side="SELL",
            order_type="LIMIT",
            status="PENDING",
            quantity=5,
            filled_quantity=0,
            limit_price=Decimal("450"),
        ),
        PaperOrderModel(
            id=second_id,
            account_id=account_id,
            symbol="AAPL",
            side="BUY",
            order_type="MARKET",
            status="FILLED",
            quantity=10,
            filled_quantity=10,
            limit_price=None,
        ),
    ]

    session.scalars.return_value.all.return_value = models

    repository = PaperOrderRepository(
        session
    )

    orders = repository.list_by_account(
        account_id,
        limit=25,
    )

    assert len(orders) == 2

    assert orders[0].order_id == first_id
    assert orders[0].symbol == "MSFT"
    assert orders[0].side == OrderSide.SELL
    assert orders[0].order_type == OrderType.LIMIT
    assert orders[0].status == OrderStatus.PENDING

    assert orders[1].order_id == second_id
    assert orders[1].symbol == "AAPL"
    assert orders[1].side == OrderSide.BUY
    assert orders[1].order_type == OrderType.MARKET
    assert orders[1].status == OrderStatus.FILLED

    statement = session.scalars.call_args.args[0]

    assert statement._limit_clause is not None
    assert statement._limit_clause.value == 25

    sql = str(
        statement
    )

    assert "paper_orders.account_id" in sql
    assert "paper_orders.created_at DESC" in sql


def test_order_repository_lists_only_open_orders() -> None:
    session = Mock()

    account_id = uuid4()

    order_id = uuid4()

    model = PaperOrderModel(
        id=order_id,
        account_id=account_id,
        symbol="AAPL",
        side="BUY",
        order_type="LIMIT",
        status="PENDING",
        quantity=10,
        filled_quantity=0,
        limit_price=Decimal("200"),
    )

    session.scalars.return_value.all.return_value = [
        model
    ]

    repository = PaperOrderRepository(
        session
    )

    orders = repository.list_open_by_account(
        account_id,
        limit=50,
    )

    assert len(orders) == 1
    assert orders[0].order_id == order_id
    assert orders[0].status == OrderStatus.PENDING

    statement = session.scalars.call_args.args[0]

    compiled = statement.compile()

    expected_statuses = {
        "NEW",
        "PENDING",
        "PARTIALLY_FILLED",
    }

    assert any(
        isinstance(value, list)
        and set(value) == expected_statuses
        for value in compiled.params.values()
    )

    assert statement._limit_clause is not None
    assert statement._limit_clause.value == 50


@pytest.mark.parametrize(
    "limit",
    [
        0,
        -1,
        501,
    ],
)
def test_order_repository_rejects_invalid_read_limit(
    limit: int,
) -> None:
    session = Mock()

    repository = PaperOrderRepository(
        session
    )

    with pytest.raises(
        ValueError,
        match="Read limit must be between 1 and 500",
    ):
        repository.list_by_account(
            uuid4(),
            limit=limit,
        )

    session.scalars.assert_not_called()


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


def test_execution_repository_lists_account_executions() -> None:
    session = Mock()

    account_id = uuid4()
    order_id = uuid4()
    execution_id = uuid4()

    model = PaperExecutionModel(
        id=execution_id,
        order_id=order_id,
        account_id=account_id,
        symbol="AAPL",
        side="BUY",
        quantity=10,
        price=Decimal("199"),
    )

    session.scalars.return_value.all.return_value = [
        model
    ]

    repository = PaperExecutionRepository(
        session
    )

    executions = repository.list_by_account(
        account_id,
        limit=10,
    )

    assert len(executions) == 1

    execution = executions[0]

    assert execution.execution_id == execution_id
    assert execution.order_id == order_id
    assert execution.symbol == "AAPL"
    assert execution.side == OrderSide.BUY
    assert execution.quantity == 10
    assert execution.price == Decimal("199")

    statement = session.scalars.call_args.args[0]

    assert statement._limit_clause is not None
    assert statement._limit_clause.value == 10

    sql = str(
        statement
    )

    assert "paper_executions.account_id" in sql
    assert "paper_executions.executed_at DESC" in sql


@pytest.mark.parametrize(
    "limit",
    [
        0,
        -1,
        501,
    ],
)
def test_execution_repository_rejects_invalid_read_limit(
    limit: int,
) -> None:
    session = Mock()

    repository = PaperExecutionRepository(
        session
    )

    with pytest.raises(
        ValueError,
        match="Read limit must be between 1 and 500",
    ):
        repository.list_by_account(
            uuid4(),
            limit=limit,
        )

    session.scalars.assert_not_called()
