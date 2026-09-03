from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from libs.database.repositories import PortfolioRepository
from libs.domain.market import Market
from libs.domain.portfolio import (
    Currency,
    Portfolio,
    Position,
)


class PortfolioNotFoundError(Exception):
    """
    Raised when a requested portfolio does not exist.
    """


class PositionAlreadyExistsError(Exception):
    """
    Raised when a portfolio already contains the instrument.
    """


class PortfolioService:
    """
    Application service for portfolio operations.

    Responsibilities:
    - Apply application/business rules.
    - Coordinate repository operations.
    - Own transaction commit/rollback.

    SQL belongs in Repository, not here.
    """

    def __init__(
        self,
        session: Session,
    ) -> None:
        self._session = session
        self._repository = PortfolioRepository(
            session
        )

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

        try:
            result = (
                self._repository
                .create_portfolio(
                    portfolio
                )
            )

            self._session.commit()

            return result

        except Exception:
            self._session.rollback()
            raise

    def get_portfolio(
        self,
        *,
        portfolio_id: UUID,
    ) -> Portfolio:
        portfolio = (
            self._repository
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
        return (
            self._repository
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
        portfolio = (
            self._repository
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
            self._repository
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
                f"{symbol.strip().upper()}"
            )

        position = Position(
            symbol=symbol,
            market=market,
            quantity=quantity,
            average_cost=average_cost,
        )

        try:
            result = (
                self._repository
                .add_position(
                    portfolio_id=portfolio_id,
                    position=position,
                )
            )

            self._session.commit()

            return result

        except Exception:
            self._session.rollback()
            raise

    def list_positions(
        self,
        *,
        portfolio_id: UUID,
    ) -> list[Position]:
        portfolio = (
            self._repository
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
            self._repository
            .list_positions(
                portfolio_id=portfolio_id
            )
        )