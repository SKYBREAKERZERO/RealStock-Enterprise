from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from libs.domain.market import Market
from libs.domain.valuation import (
    PortfolioValuation,
    PositionValuation,
)


class PositionValuationResponse(BaseModel):
    position_id: UUID

    symbol: str
    market: Market

    quantity: Decimal
    average_cost: Decimal
    cost_basis: Decimal

    market_price: Decimal | None
    market_value: Decimal | None

    unrealized_pnl: Decimal | None
    unrealized_pnl_percent: Decimal | None

    quote_timestamp: datetime | None

    quote_available: bool

    @classmethod
    def from_domain(
        cls,
        valuation: PositionValuation,
    ) -> PositionValuationResponse:
        return cls(
            position_id=valuation.position_id,
            symbol=valuation.symbol,
            market=valuation.market,
            quantity=valuation.quantity,
            average_cost=valuation.average_cost,
            cost_basis=valuation.cost_basis,
            market_price=valuation.market_price,
            market_value=valuation.market_value,
            unrealized_pnl=valuation.unrealized_pnl,
            unrealized_pnl_percent=(
                valuation.unrealized_pnl_percent
            ),
            quote_timestamp=(
                valuation.quote_timestamp
            ),
            quote_available=(
                valuation.quote_available
            ),
        )


class PortfolioValuationResponse(BaseModel):
    portfolio_id: UUID

    total_cost_basis: Decimal
    priced_cost_basis: Decimal

    total_market_value: Decimal
    total_unrealized_pnl: Decimal

    priced_positions: int
    missing_quotes: int

    valuation_complete: bool

    positions: list[
        PositionValuationResponse
    ]

    @classmethod
    def from_domain(
        cls,
        valuation: PortfolioValuation,
    ) -> PortfolioValuationResponse:
        return cls(
            portfolio_id=valuation.portfolio_id,
            total_cost_basis=(
                valuation.total_cost_basis
            ),
            priced_cost_basis=(
                valuation.priced_cost_basis
            ),
            total_market_value=(
                valuation.total_market_value
            ),
            total_unrealized_pnl=(
                valuation.total_unrealized_pnl
            ),
            priced_positions=(
                valuation.priced_positions
            ),
            missing_quotes=(
                valuation.missing_quotes
            ),
            valuation_complete=(
                valuation.valuation_complete
            ),
            positions=[
                PositionValuationResponse.from_domain(
                    position
                )
                for position
                in valuation.positions
            ],
        )