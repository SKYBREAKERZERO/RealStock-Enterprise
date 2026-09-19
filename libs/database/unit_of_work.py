from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self

from sqlalchemy.orm import Session

from libs.database.repositories import (
    OutboxRepository,
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

    def commit(self) -> None:
        ...

    def rollback(self) -> None:
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

    This allows business data and transactional outbox events to
    participate in the same PostgreSQL transaction.
    """

    def __init__(
        self,
        session: Session,
    ) -> None:
        self._session = session

        self.portfolios = PortfolioRepository(
            session,
        )

        self.outbox = OutboxRepository(
            session,
        )

        self._committed = False
        self._rolled_back = False

    def __enter__(
        self,
    ) -> SqlAlchemyUnitOfWork:
        self._committed = False
        self._rolled_back = False

        return self

    def commit(self) -> None:
        """
        Commit all repository work participating in this Unit of Work.
        """

        try:
            self._session.commit()
        except Exception:
            self.rollback()
            raise

        self._committed = True

    def rollback(self) -> None:
        """
        Roll back all uncommitted work.
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
        Roll back on exceptions or when the context exits
        without an explicit commit.
        """

        if exc_type is not None:
            if not self._committed:
                self.rollback()

            return

        if not self._committed:
            self.rollback()