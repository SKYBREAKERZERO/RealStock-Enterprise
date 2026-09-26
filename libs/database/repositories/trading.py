from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from libs.database.models import (
    PaperAccountModel,
    PaperExecutionModel,
    PaperOrderModel,
    PaperPositionModel,
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
    Position,
)

_DEFAULT_READ_LIMIT = 100
_MAX_READ_LIMIT = 500

_OPEN_ORDER_STATUSES = (
    OrderStatus.NEW,
    OrderStatus.PENDING,
    OrderStatus.PARTIALLY_FILLED,
)


def _validate_read_limit(
    limit: int,
) -> int:
    if not 1 <= limit <= _MAX_READ_LIMIT:
        raise ValueError(
            "Read limit must be between "
            f"1 and {_MAX_READ_LIMIT}."
        )

    return limit


class PaperAccountRepository:
    def __init__(
        self,
        session: Session,
    ) -> None:
        self._session = session

    def add(
        self,
        *,
        user_id: str,
        account: PaperAccount,
    ) -> None:
        model = PaperAccountModel(
            id=account.account_id,
            user_id=user_id,
            initial_cash=account.initial_cash,
            cash_balance=account.cash_balance,
        )

        self._session.add(
            model
        )

    def get(
        self,
        account_id: UUID,
    ) -> PaperAccount | None:
        model = self._session.get(
            PaperAccountModel,
            account_id,
        )

        if model is None:
            return None

        return self._to_domain(
            model
        )

    def get_by_user_id(
        self,
        user_id: str,
    ) -> PaperAccount | None:
        normalized_user_id = (
            user_id
            .strip()
        )

        if not normalized_user_id:
            raise ValueError(
                "User ID must not be empty."
            )

        statement = (
            select(
                PaperAccountModel
            )
            .where(
                PaperAccountModel.user_id
                == normalized_user_id,
            )
        )

        model = self._session.scalar(
            statement
        )

        if model is None:
            return None

        return self._to_domain(
            model
        )

    def get_for_update(
        self,
        account_id: UUID,
    ) -> PaperAccount | None:
        """
        Load an account using SELECT ... FOR UPDATE.

        The row lock is held until the surrounding transaction
        commits or rolls back.
        """

        statement = (
            select(
                PaperAccountModel
            )
            .where(
                PaperAccountModel.id
                == account_id,
            )
            .with_for_update()
        )

        model = self._session.scalar(
            statement
        )

        if model is None:
            return None

        return self._to_domain(
            model
        )

    def update(
        self,
        account: PaperAccount,
    ) -> None:
        model = self._session.get(
            PaperAccountModel,
            account.account_id,
        )

        if model is None:
            raise ValueError(
                f"Paper account {account.account_id} not found."
            )

        model.cash_balance = account.cash_balance

    @staticmethod
    def _to_domain(
        model: PaperAccountModel,
    ) -> PaperAccount:
        return PaperAccount(
            account_id=model.id,
            initial_cash=model.initial_cash,
            cash_balance=model.cash_balance,
        )


class PaperPositionRepository:
    def __init__(
        self,
        session: Session,
    ) -> None:
        self._session = session

    def get(
        self,
        *,
        account_id: UUID,
        symbol: str,
    ) -> Position | None:
        normalized_symbol = (
            symbol
            .strip()
            .upper()
        )

        statement = (
            select(
                PaperPositionModel
            )
            .where(
                PaperPositionModel.account_id
                == account_id,
                PaperPositionModel.symbol
                == normalized_symbol,
            )
        )

        model = self._session.scalar(
            statement
        )

        if model is None:
            return None

        return self._to_domain(
            model
        )

    def get_for_update(
        self,
        *,
        account_id: UUID,
        symbol: str,
    ) -> Position | None:
        """
        Load a position using SELECT ... FOR UPDATE.

        Existing positions are pessimistically locked until the
        surrounding transaction commits or rolls back.
        """

        normalized_symbol = (
            symbol
            .strip()
            .upper()
        )

        statement = (
            select(
                PaperPositionModel
            )
            .where(
                PaperPositionModel.account_id
                == account_id,
                PaperPositionModel.symbol
                == normalized_symbol,
            )
            .with_for_update()
        )

        model = self._session.scalar(
            statement
        )

        if model is None:
            return None

        return self._to_domain(
            model
        )

    def list_by_account(
        self,
        account_id: UUID,
    ) -> list[Position]:
        statement = (
            select(
                PaperPositionModel
            )
            .where(
                PaperPositionModel.account_id
                == account_id,
            )
            .order_by(
                PaperPositionModel.symbol.asc(),
            )
        )

        models = self._session.scalars(
            statement
        ).all()

        return [
            self._to_domain(
                model
            )
            for model in models
        ]

    def upsert(
        self,
        *,
        account_id: UUID,
        position: Position,
    ) -> None:
        normalized_symbol = (
            position.symbol
            .strip()
            .upper()
        )

        statement = (
            select(
                PaperPositionModel
            )
            .where(
                PaperPositionModel.account_id
                == account_id,
                PaperPositionModel.symbol
                == normalized_symbol,
            )
        )

        model = self._session.scalar(
            statement
        )

        if model is None:
            model = PaperPositionModel(
                account_id=account_id,
                symbol=normalized_symbol,
                quantity=position.quantity,
                average_cost=position.average_cost,
                realized_pnl=position.realized_pnl,
            )

            self._session.add(
                model
            )

            return

        model.quantity = position.quantity
        model.average_cost = position.average_cost
        model.realized_pnl = position.realized_pnl

    @staticmethod
    def _to_domain(
        model: PaperPositionModel,
    ) -> Position:
        return Position(
            symbol=model.symbol,
            quantity=model.quantity,
            average_cost=model.average_cost,
            realized_pnl=model.realized_pnl,
        )


class PaperOrderRepository:
    def __init__(
        self,
        session: Session,
    ) -> None:
        self._session = session

    def add(
        self,
        order: PaperOrder,
    ) -> None:
        model = PaperOrderModel(
            id=order.order_id,
            account_id=order.account_id,
            symbol=order.symbol,
            side=order.side.value,
            order_type=order.order_type.value,
            status=order.status.value,
            quantity=order.quantity,
            filled_quantity=order.filled_quantity,
            limit_price=order.limit_price,
        )

        self._session.add(
            model
        )

        # paper_executions.order_id references paper_orders.id.
        #
        # Flush the order before an execution is inserted so that
        # PostgreSQL can satisfy the foreign-key dependency.
        #
        # flush() does not commit. UnitOfWork remains responsible
        # for the transaction boundary.
        self._session.flush()

    def get(
        self,
        order_id: UUID,
    ) -> PaperOrder | None:
        model = self._session.get(
            PaperOrderModel,
            order_id,
        )

        if model is None:
            return None

        return self._to_domain(
            model
        )

    def get_for_update(
        self,
        order_id: UUID,
    ) -> PaperOrder | None:
        """
        Load an order using SELECT ... FOR UPDATE.

        This lock protects a persisted PENDING LIMIT order from
        concurrent processing.

        The row lock remains held until the surrounding UnitOfWork
        transaction commits or rolls back.
        """

        statement = (
            select(
                PaperOrderModel
            )
            .where(
                PaperOrderModel.id
                == order_id,
            )
            .with_for_update()
        )

        model = self._session.scalar(
            statement
        )

        if model is None:
            return None

        return self._to_domain(
            model
        )

    def list_by_account(
        self,
        account_id: UUID,
        *,
        limit: int = _DEFAULT_READ_LIMIT,
    ) -> list[PaperOrder]:
        validated_limit = _validate_read_limit(
            limit
        )

        statement = (
            select(
                PaperOrderModel
            )
            .where(
                PaperOrderModel.account_id
                == account_id,
            )
            .order_by(
                PaperOrderModel.created_at.desc(),
                PaperOrderModel.id.desc(),
            )
            .limit(
                validated_limit
            )
        )

        models = self._session.scalars(
            statement
        ).all()

        return [
            self._to_domain(
                model
            )
            for model in models
        ]

    def list_open_by_account(
        self,
        account_id: UUID,
        *,
        limit: int = _DEFAULT_READ_LIMIT,
    ) -> list[PaperOrder]:
        validated_limit = _validate_read_limit(
            limit
        )

        open_status_values = [
            status.value
            for status in _OPEN_ORDER_STATUSES
        ]

        statement = (
            select(
                PaperOrderModel
            )
            .where(
                PaperOrderModel.account_id
                == account_id,
                PaperOrderModel.status.in_(
                    open_status_values
                ),
            )
            .order_by(
                PaperOrderModel.created_at.desc(),
                PaperOrderModel.id.desc(),
            )
            .limit(
                validated_limit
            )
        )

        models = self._session.scalars(
            statement
        ).all()

        return [
            self._to_domain(
                model
            )
            for model in models
        ]

    def update(
        self,
        order: PaperOrder,
    ) -> None:
        model = self._session.get(
            PaperOrderModel,
            order.order_id,
        )

        if model is None:
            raise ValueError(
                f"Paper order {order.order_id} not found."
            )

        model.status = order.status.value
        model.filled_quantity = order.filled_quantity
        model.limit_price = order.limit_price

    @staticmethod
    def _to_domain(
        model: PaperOrderModel,
    ) -> PaperOrder:
        return PaperOrder(
            order_id=model.id,
            account_id=model.account_id,
            symbol=model.symbol,
            side=OrderSide(
                model.side
            ),
            quantity=model.quantity,
            order_type=OrderType(
                model.order_type
            ),
            status=OrderStatus(
                model.status
            ),
            filled_quantity=model.filled_quantity,
            limit_price=model.limit_price,
        )


class PaperExecutionRepository:
    def __init__(
        self,
        session: Session,
    ) -> None:
        self._session = session

    def add(
        self,
        *,
        account_id: UUID,
        execution: Execution,
    ) -> None:
        model = PaperExecutionModel(
            id=execution.execution_id,
            order_id=execution.order_id,
            account_id=account_id,
            symbol=execution.symbol,
            side=execution.side.value,
            quantity=execution.quantity,
            price=execution.price,
        )

        self._session.add(
            model
        )

    def list_by_account(
        self,
        account_id: UUID,
        *,
        limit: int = _DEFAULT_READ_LIMIT,
    ) -> list[Execution]:
        validated_limit = _validate_read_limit(
            limit
        )

        statement = (
            select(
                PaperExecutionModel
            )
            .where(
                PaperExecutionModel.account_id
                == account_id,
            )
            .order_by(
                PaperExecutionModel.executed_at.desc(),
                PaperExecutionModel.id.desc(),
            )
            .limit(
                validated_limit
            )
        )

        models = self._session.scalars(
            statement
        ).all()

        return [
            self._to_domain(
                model
            )
            for model in models
        ]

    @staticmethod
    def _to_domain(
        model: PaperExecutionModel,
    ) -> Execution:
        return Execution(
            execution_id=model.id,
            order_id=model.order_id,
            symbol=model.symbol,
            side=OrderSide(
                model.side
            ),
            quantity=model.quantity,
            price=model.price,
        )
