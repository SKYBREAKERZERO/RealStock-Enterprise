from __future__ import annotations

from datetime import UTC, datetime
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
from libs.events.portfolio import (
    create_portfolio_created_event,
    create_position_added_event,
    create_position_removed_event,
    create_position_updated_event,
)

_POSITION_UNIQUE_CONSTRAINT = (
    "uq_positions_portfolio_market_symbol"
)


class PortfolioNotFoundError(Exception):
    """
    Raised when a requested portfolio does not exist.
    """


class PositionNotFoundError(Exception):
    """
    Raised when a requested position does not exist.
    """


class PositionAlreadyExistsError(Exception):
    """
    Raised when a portfolio already contains the instrument.
    """


def _get_constraint_name(
    error: IntegrityError,
) -> str | None:
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

    Business writes and their corresponding outbox events are
    committed atomically through the same Unit of Work.
    """

    def __init__(
        self,
        unit_of_work: UnitOfWork,
    ) -> None:
        self._uow = unit_of_work

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

            event = (
                create_portfolio_created_event(
                    result
                )
            )

            self._uow.outbox.add_event(
                aggregate_type="portfolio",
                aggregate_id=str(
                    result.portfolio_id
                ),
                event=event,
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

                event = (
                    create_position_added_event(
                        portfolio_id=portfolio_id,
                        position=result,
                    )
                )

                self._uow.outbox.add_event(
                    aggregate_type="portfolio",
                    aggregate_id=str(
                        portfolio_id
                    ),
                    event=event,
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

    def update_position(
        self,
        *,
        portfolio_id: UUID,
        position_id: UUID,
        quantity: Decimal | None = None,
        average_cost: Decimal | None = None,
    ) -> Position:
        if (
            quantity is None
            and average_cost is None
        ):
            raise ValueError(
                "at least one position field must be provided"
            )

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
                .get_position_by_id(
                    portfolio_id=portfolio_id,
                    position_id=position_id,
                    for_update=True,
                )
            )

            if existing is None:
                raise PositionNotFoundError(
                    f"position not found: "
                    f"{position_id}"
                )

            updated = Position(
                position_id=existing.position_id,
                symbol=existing.symbol,
                market=existing.market,
                quantity=(
                    quantity
                    if quantity is not None
                    else existing.quantity
                ),
                average_cost=(
                    average_cost
                    if average_cost is not None
                    else existing.average_cost
                ),
                created_at=existing.created_at,
                updated_at=datetime.now(UTC),
            )

            result = (
                self._uow
                .portfolios
                .update_position(
                    portfolio_id=portfolio_id,
                    position=updated,
                )
            )

            if result is None:
                raise PositionNotFoundError(
                    f"position not found: "
                    f"{position_id}"
                )

            event = (
                create_position_updated_event(
                    portfolio_id=portfolio_id,
                    previous_position=existing,
                    position=result,
                )
            )

            self._uow.outbox.add_event(
                aggregate_type="portfolio",
                aggregate_id=str(
                    portfolio_id
                ),
                event=event,
            )

            self._uow.commit()

            return result

    def delete_position(
        self,
        *,
        portfolio_id: UUID,
        position_id: UUID,
    ) -> None:
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
                .get_position_by_id(
                    portfolio_id=portfolio_id,
                    position_id=position_id,
                    for_update=True,
                )
            )

            if existing is None:
                raise PositionNotFoundError(
                    f"position not found: "
                    f"{position_id}"
                )

            removed_at = datetime.now(
                UTC
            )

            deleted = (
                self._uow
                .portfolios
                .delete_position(
                    portfolio_id=portfolio_id,
                    position_id=position_id,
                    removed_at=removed_at,
                )
            )

            if deleted is None:
                raise PositionNotFoundError(
                    f"position not found: "
                    f"{position_id}"
                )

            event = (
                create_position_removed_event(
                    portfolio_id=portfolio_id,
                    position=deleted,
                    removed_at=removed_at,
                )
            )

            self._uow.outbox.add_event(
                aggregate_type="portfolio",
                aggregate_id=str(
                    portfolio_id
                ),
                event=event,
            )

            self._uow.commit()

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
