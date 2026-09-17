from __future__ import annotations

from types import TracebackType
from typing import Protocol, Self

from sqlalchemy.orm import Session

from libs.database.repositories import PortfolioRepository


class UnitOfWork(Protocol):
    """
    Transaction boundary contract used by application services.

    Implementations coordinate repositories that participate in
    the same database transaction.
    """

    portfolios: PortfolioRepository

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
    - Commit must be explicit.
    - Exceptions trigger rollback.
    - Leaving without commit triggers rollback.
    - Session lifecycle is owned externally.
    """

    def __init__(
        self,
        session: Session,
    ) -> None:
        self._session = session
        self.portfolios = PortfolioRepository(
            session
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
        try:
            self._session.commit()
        except Exception:
            self.rollback()
            raise

        self._committed = True

    def rollback(self) -> None:
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
        if exc_type is not None:
            self.rollback()
            return

        if not self._committed:
            self.rollback()