from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy.exc import IntegrityError

from libs.database.unit_of_work import UnitOfWork
from libs.domain.market import Market
from libs.domain.portfolio import (
    Currency,
    Portfolio,
    Position,
)


_POSITION_UNIQUE_CONSTRAINT = (
    "uq_positions_portfolio_market_symbol"
)


class PortfolioNotFoundError(Exception):
    """
    Raised when a requested portfolio does not exist.
    """


class PositionAlreadyExistsError(Exception):
    """
    Raised when a portfolio already contains the instrument.
    """


def _get_constraint_name(
    error: IntegrityError,
) -> str | None:
    """
    Return the database constraint name carried by the
    underlying PostgreSQL driver exception.

    PostgreSQL / psycopg exposes constraint metadata through
    the driver's diagnostic object.

    If the constraint name cannot be determined, return None
    so the original database error can propagate unchanged.
    """

    diag = getattr(
        error.orig,
        "diag",
        None,
    )

    if diag is None:
        return None

    return getattr(
        diag,
        "constraint_name",
        None,
    )


class PortfolioService:
    """
    Application service for portfolio operations.

    Responsibilities:
    - Apply application/business rules.
    - Coordinate repository operations through Unit of Work.
    - Define explicit transaction success boundaries.
    - Translate known persistence conflicts into application
      errors without leaking database implementation details.

    SQL and persistence details belong in Repository.
    Transaction mechanics belong in Unit of Work.
    """

    def __init__(
        self,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._uow = unit_of_work

    # ==========================================================
    # Portfolio
    # ==========================================================

    def create_portfolio(
        self,
        *,
        user_id: str,
        name: str,
        currency: Currency = Currency.USD,
    ) -> Portfolio:
        portfolio = Portfolio(
            user_id=user_id,
            name=name,
            currency=currency,
        )

        with self._uow:
            result = (
                self._uow
                .portfolios
                .create_portfolio(
                    portfolio
                )
            )

            self._uow.commit()

            return result

    def get_portfolio(
        self,
        *,
        portfolio_id: UUID,
    ) -> Portfolio:
        with self._uow:
            portfolio = (
                self._uow
                .portfolios
                .get_portfolio(
                    portfolio_id
                )
            )

            if portfolio is None:
                raise PortfolioNotFoundError(
                    f"portfolio not found: "
                    f"{portfolio_id}"
                )

            return portfolio

    def list_portfolios(
        self,
        *,
        user_id: str,
    ) -> list[Portfolio]:
        with self._uow:
            return (
                self._uow
                .portfolios
                .list_portfolios(
                    user_id=user_id
                )
            )

    # ==========================================================
    # Position
    # ==========================================================

    def add_position(
        self,
        *,
        portfolio_id: UUID,
        symbol: str,
        market: Market,
        quantity: Decimal,
        average_cost: Decimal,
    ) -> Position:
        normalized_symbol = (
            symbol.strip().upper()
        )

        try:
            with self._uow:
                portfolio = (
                    self._uow
                    .portfolios
                    .get_portfolio(
                        portfolio_id
                    )
                )

                if portfolio is None:
                    raise PortfolioNotFoundError(
                        f"portfolio not found: "
                        f"{portfolio_id}"
                    )

                existing = (
                    self._uow
                    .portfolios
                    .get_position(
                        portfolio_id=portfolio_id,
                        market=market,
                        symbol=symbol,
                    )
                )

                if existing is not None:
                    raise PositionAlreadyExistsError(
                        "position already exists: "
                        f"{market.value}:"
                        f"{normalized_symbol}"
                    )

                position = Position(
                    symbol=symbol,
                    market=market,
                    quantity=quantity,
                    average_cost=average_cost,
                )

                result = (
                    self._uow
                    .portfolios
                    .add_position(
                        portfolio_id=portfolio_id,
                        position=position,
                    )
                )

                self._uow.commit()

                return result

        except IntegrityError as exc:
            constraint_name = (
                _get_constraint_name(
                    exc
                )
            )

            if (
                constraint_name
                == _POSITION_UNIQUE_CONSTRAINT
            ):
                raise PositionAlreadyExistsError(
                    "position already exists: "
                    f"{market.value}:"
                    f"{normalized_symbol}"
                ) from exc

            raise

    def list_positions(
        self,
        *,
        portfolio_id: UUID,
    ) -> list[Position]:
        with self._uow:
            portfolio = (
                self._uow
                .portfolios
                .get_portfolio(
                    portfolio_id
                )
            )

            if portfolio is None:
                raise PortfolioNotFoundError(
                    f"portfolio not found: "
                    f"{portfolio_id}"
                )

            return (
                self._uow
                .portfolios
                .list_positions(
                    portfolio_id=portfolio_id
                )
            )