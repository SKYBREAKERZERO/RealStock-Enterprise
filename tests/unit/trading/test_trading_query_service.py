from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from libs.trading.enums import (
    OrderSide,
    OrderStatus,
    OrderType,
)
from libs.trading.execution import Execution
from libs.trading.models import (
    PaperAccount,
    PaperOrder,
    Position,
)
from services.trading.trading_query_service import (
    TradingQueryService,
)


def build_uow(
    *,
    account: PaperAccount | None,
) -> MagicMock:
    uow = MagicMock()

    uow.__enter__.return_value = uow
    uow.__exit__.return_value = None

    uow.paper_accounts.get_by_user_id.return_value = (
        account
    )

    return uow


def test_get_account_returns_user_account() -> None:
    account = PaperAccount(
        initial_cash=Decimal("100000"),
    )

    uow = build_uow(
        account=account,
    )

    service = TradingQueryService(
        unit_of_work=uow,
    )

    result = service.get_account(
        user_id="user-001",
    )

    assert result is account

    (
        uow.paper_accounts
        .get_by_user_id
        .assert_called_once_with(
            "user-001"
        )
    )

    uow.commit.assert_not_called()

    (
        uow.paper_accounts
        .get_for_update
        .assert_not_called()
    )


def test_get_account_returns_none_when_missing() -> None:
    uow = build_uow(
        account=None,
    )

    service = TradingQueryService(
        unit_of_work=uow,
    )

    result = service.get_account(
        user_id="missing-user",
    )

    assert result is None

    uow.commit.assert_not_called()


def test_list_positions_reads_account_positions() -> None:
    account = PaperAccount(
        initial_cash=Decimal("100000"),
    )

    positions = [
        Position(
            symbol="AAPL",
            quantity=10,
            average_cost=Decimal("200"),
            realized_pnl=Decimal("25"),
        ),
        Position(
            symbol="MSFT",
            quantity=5,
            average_cost=Decimal("410"),
            realized_pnl=Decimal("-10"),
        ),
    ]

    uow = build_uow(
        account=account,
    )

    (
        uow.paper_positions
        .list_by_account
        .return_value
    ) = positions

    service = TradingQueryService(
        unit_of_work=uow,
    )

    result = service.list_positions(
        user_id="user-001",
    )

    assert result == positions

    (
        uow.paper_positions
        .list_by_account
        .assert_called_once_with(
            account.account_id
        )
    )

    (
        uow.paper_positions
        .get_for_update
        .assert_not_called()
    )

    uow.commit.assert_not_called()


def test_list_orders_reads_history_with_limit() -> None:
    account = PaperAccount(
        initial_cash=Decimal("100000"),
    )

    order = PaperOrder(
        account_id=account.account_id,
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=10,
        order_type=OrderType.MARKET,
        status=OrderStatus.FILLED,
        filled_quantity=10,
    )

    uow = build_uow(
        account=account,
    )

    (
        uow.paper_orders
        .list_by_account
        .return_value
    ) = [
        order
    ]

    service = TradingQueryService(
        unit_of_work=uow,
    )

    result = service.list_orders(
        user_id="user-001",
        limit=25,
    )

    assert result == [
        order
    ]

    (
        uow.paper_orders
        .list_by_account
        .assert_called_once_with(
            account.account_id,
            limit=25,
        )
    )

    (
        uow.paper_orders
        .get_for_update
        .assert_not_called()
    )

    uow.commit.assert_not_called()


def test_list_open_orders_reads_open_history() -> None:
    account = PaperAccount(
        initial_cash=Decimal("100000"),
    )

    order = PaperOrder(
        account_id=account.account_id,
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=10,
        order_type=OrderType.LIMIT,
        status=OrderStatus.PENDING,
        filled_quantity=0,
        limit_price=Decimal("200"),
    )

    uow = build_uow(
        account=account,
    )

    (
        uow.paper_orders
        .list_open_by_account
        .return_value
    ) = [
        order
    ]

    service = TradingQueryService(
        unit_of_work=uow,
    )

    result = service.list_open_orders(
        user_id="user-001",
        limit=50,
    )

    assert result == [
        order
    ]

    (
        uow.paper_orders
        .list_open_by_account
        .assert_called_once_with(
            account.account_id,
            limit=50,
        )
    )

    (
        uow.paper_orders
        .get_for_update
        .assert_not_called()
    )

    uow.commit.assert_not_called()


def test_list_executions_reads_execution_history() -> None:
    account = PaperAccount(
        initial_cash=Decimal("100000"),
    )

    order_id = uuid4()

    execution = Execution(
        order_id=order_id,
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=10,
        price=Decimal("199"),
    )

    uow = build_uow(
        account=account,
    )

    (
        uow.paper_executions
        .list_by_account
        .return_value
    ) = [
        execution
    ]

    service = TradingQueryService(
        unit_of_work=uow,
    )

    result = service.list_executions(
        user_id="user-001",
        limit=10,
    )

    assert result == [
        execution
    ]

    (
        uow.paper_executions
        .list_by_account
        .assert_called_once_with(
            account.account_id,
            limit=10,
        )
    )

    uow.commit.assert_not_called()


@pytest.mark.parametrize(
    "operation",
    [
        "positions",
        "orders",
        "open_orders",
        "executions",
    ],
)
def test_account_scoped_queries_reject_missing_account(
    operation: str,
) -> None:
    uow = build_uow(
        account=None,
    )

    service = TradingQueryService(
        unit_of_work=uow,
    )

    with pytest.raises(
        ValueError,
        match="Paper account for user",
    ):
        if operation == "positions":
            service.list_positions(
                user_id="missing-user",
            )

        elif operation == "orders":
            service.list_orders(
                user_id="missing-user",
            )

        elif operation == "open_orders":
            service.list_open_orders(
                user_id="missing-user",
            )

        else:
            service.list_executions(
                user_id="missing-user",
            )

    (
        uow.paper_positions
        .list_by_account
        .assert_not_called()
    )

    (
        uow.paper_orders
        .list_by_account
        .assert_not_called()
    )

    (
        uow.paper_orders
        .list_open_by_account
        .assert_not_called()
    )

    (
        uow.paper_executions
        .list_by_account
        .assert_not_called()
    )

    uow.commit.assert_not_called()
