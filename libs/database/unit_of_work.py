from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self

from sqlalchemy.orm import Session

from libs.database.repositories import (
    OutboxRepository,
    PaperAccountRepository,
    PaperExecutionRepository,
    PaperOrderRepository,
    PaperPositionRepository,
    PortfolioRepository,
)


class UnitOfWork(Protocol):
    """
    Transaction boundary contract used by application services.

    Implementations coordinate repositories that participate in
    the same database transaction.

    All repositories exposed by the Unit of Work must share the
    same database session so their writes can be committed or
    rolled back atomically.
    """

    portfolios: PortfolioRepository
    outbox: OutboxRepository

    paper_accounts: PaperAccountRepository
    paper_positions: PaperPositionRepository
    paper_orders: PaperOrderRepository
    paper_executions: PaperExecutionRepository

    def __enter__(
        self,
    ) -> Self:
        ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        ...

    def commit(
        self,
    ) -> None:
        ...

    def rollback(
        self,
    ) -> None:
        ...


class SqlAlchemyUnitOfWork:
    """
    SQLAlchemy-backed Unit of Work.

    Transaction policy:
    - All repositories share the same SQLAlchemy Session.
    - Commit must be explicit.
    - Exceptions trigger rollback.
    - Leaving the context without commit triggers rollback.
    - Commit failures trigger rollback.
    - Session lifecycle is owned externally.

    This allows business data, paper-trading state, executions,
    and transactional outbox events to participate in the same
    PostgreSQL transaction.
    """

    def __init__(
        self,
        session: Session,
    ) -> None:
        self._session = session

        # ======================================================
        # Portfolio
        # ======================================================

        self.portfolios = PortfolioRepository(
            session,
        )

        # ======================================================
        # Paper Trading
        # ======================================================

        self.paper_accounts = PaperAccountRepository(
            session,
        )

        self.paper_positions = PaperPositionRepository(
            session,
        )

        self.paper_orders = PaperOrderRepository(
            session,
        )

        self.paper_executions = PaperExecutionRepository(
            session,
        )

        # ======================================================
        # Transactional Outbox
        # ======================================================

        self.outbox = OutboxRepository(
            session,
        )

        # ======================================================
        # Transaction State
        # ======================================================

        self._committed = False
        self._rolled_back = False

    def __enter__(
        self,
    ) -> SqlAlchemyUnitOfWork:
        """
        Enter a new Unit of Work scope.

        Repository instances remain bound to the externally owned
        SQLAlchemy Session. Only transaction state flags are reset
        for the new application-service operation.
        """

        self._committed = False
        self._rolled_back = False

        return self

    def commit(
        self,
    ) -> None:
        """
        Commit all repository work participating in this Unit of Work.

        If the commit fails, the transaction is rolled back before
        the exception is propagated to the caller.
        """

        try:
            self._session.commit()

        except Exception:
            self.rollback()
            raise

        self._committed = True

    def rollback(
        self,
    ) -> None:
        """
        Roll back all uncommitted work.

        Rollback is idempotent within the current Unit of Work scope.
        """

        if self._rolled_back:
            return

        self._session.rollback()

        self._rolled_back = True

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """
        Exit the Unit of Work scope.

        Transaction semantics:

        Exception:
            rollback unless already committed.

        Normal exit without explicit commit:
            rollback.

        Normal exit after commit:
            no additional transaction action.

        Session lifecycle remains owned by the caller.
        """

        if exc_type is not None:
            if not self._committed:
                self.rollback()

            return

        if not self._committed:
            self.rollback()