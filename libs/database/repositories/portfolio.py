from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from libs.database.models.portfolio import (
    PortfolioModel,
    PositionModel,
)
from libs.domain.market import Market
from libs.domain.portfolio import (
    Currency,
    Portfolio,
    Position,
)


class PortfolioRepository:
    """
    SQLAlchemy-backed repository for Portfolio aggregates.

    Transaction policy:
    - Repository may flush.
    - Repository does NOT commit.
    - Caller owns transaction boundaries.
    """

    def __init__(
        self,
        session: Session,
    ) -> None:
        self._session = session

    # ==========================================================
    # Portfolio
    # ==========================================================

    def create_portfolio(
        self,
        portfolio: Portfolio,
    ) -> Portfolio:
        model = PortfolioModel(
            id=portfolio.portfolio_id,
            user_id=portfolio.user_id,
            name=portfolio.name,
            currency=portfolio.currency.value,
            created_at=portfolio.created_at,
            updated_at=portfolio.updated_at,
        )

        self._session.add(model)
        self._session.flush()

        return self.get_portfolio(
            portfolio.portfolio_id
        )

    def get_portfolio(
        self,
        portfolio_id: UUID,
    ) -> Portfolio | None:
        statement = (
            select(PortfolioModel)
            .options(
                selectinload(
                    PortfolioModel.positions
                )
            )
            .where(
                PortfolioModel.id
                == portfolio_id
            )
        )

        model = (
            self._session
            .execute(statement)
            .scalar_one_or_none()
        )

        if model is None:
            return None

        return self._to_domain_portfolio(
            model
        )

    def list_portfolios(
        self,
        *,
        user_id: str,
    ) -> list[Portfolio]:
        statement = (
            select(PortfolioModel)
            .options(
                selectinload(
                    PortfolioModel.positions
                )
            )
            .where(
                PortfolioModel.user_id
                == user_id
            )
            .order_by(
                PortfolioModel.created_at.asc()
            )
        )

        models = (
            self._session
            .execute(statement)
            .scalars()
            .all()
        )

        return [
            self._to_domain_portfolio(
                model
            )
            for model in models
        ]

    # ==========================================================
    # Position
    # ==========================================================

    def add_position(
        self,
        *,
        portfolio_id: UUID,
        position: Position,
    ) -> Position:
        model = PositionModel(
            id=position.position_id,
            portfolio_id=portfolio_id,
            symbol=position.symbol,
            market=position.market.value,
            quantity=position.quantity,
            average_cost=position.average_cost,
            created_at=position.created_at,
            updated_at=position.updated_at,
        )

        self._session.add(model)
        self._session.flush()

        return self._to_domain_position(
            model
        )

    def get_position(
        self,
        *,
        portfolio_id: UUID,
        market: Market,
        symbol: str,
    ) -> Position | None:
        normalized_symbol = (
            symbol.strip().upper()
        )

        statement = (
            select(PositionModel)
            .where(
                PositionModel.portfolio_id
                == portfolio_id,
                PositionModel.market
                == market.value,
                PositionModel.symbol
                == normalized_symbol,
            )
        )

        model = (
            self._session
            .execute(statement)
            .scalar_one_or_none()
        )

        if model is None:
            return None

        return self._to_domain_position(
            model
        )

    def list_positions(
        self,
        *,
        portfolio_id: UUID,
    ) -> list[Position]:
        statement = (
            select(PositionModel)
            .where(
                PositionModel.portfolio_id
                == portfolio_id
            )
            .order_by(
                PositionModel.market.asc(),
                PositionModel.symbol.asc(),
            )
        )

        models = (
            self._session
            .execute(statement)
            .scalars()
            .all()
        )

        return [
            self._to_domain_position(
                model
            )
            for model in models
        ]

    # ==========================================================
    # Mapping
    # ==========================================================

    @staticmethod
    def _to_domain_position(
        model: PositionModel,
    ) -> Position:
        return Position(
            position_id=model.id,
            symbol=model.symbol,
            market=Market(model.market),
            quantity=model.quantity,
            average_cost=model.average_cost,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @classmethod
    def _to_domain_portfolio(
        cls,
        model: PortfolioModel,
    ) -> Portfolio:
        positions = tuple(
            cls._to_domain_position(
                position
            )
            for position in model.positions
        )

        return Portfolio(
            portfolio_id=model.id,
            user_id=model.user_id,
            name=model.name,
            currency=Currency(
                model.currency
            ),
            positions=positions,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )