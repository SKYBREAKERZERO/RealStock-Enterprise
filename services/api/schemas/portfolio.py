from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from libs.domain.market import Market
from libs.domain.portfolio import (
    Currency,
    Portfolio,
    Position,
)


class CreatePortfolioRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    name: str = Field(
        min_length=1,
        max_length=100,
    )

    currency: Currency = Currency.USD


class CreatePositionRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    symbol: str = Field(
        min_length=1,
        max_length=32,
    )

    market: Market

    quantity: Decimal = Field(
        gt=Decimal("0"),
    )

    average_cost: Decimal = Field(
        gt=Decimal("0"),
    )


class UpdatePositionRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    quantity: Decimal | None = Field(
        default=None,
        gt=Decimal("0"),
    )

    average_cost: Decimal | None = Field(
        default=None,
        gt=Decimal("0"),
    )

    @model_validator(mode="after")
    def validate_at_least_one_field(
        self,
    ) -> Self:
        if (
            self.quantity is None
            and self.average_cost is None
        ):
            raise ValueError(
                "at least one position field must be provided"
            )

        return self


class PositionResponse(BaseModel):
    position_id: UUID
    symbol: str
    market: Market

    quantity: Decimal
    average_cost: Decimal
    cost_basis: Decimal

    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(
        cls,
        position: Position,
    ) -> PositionResponse:
        return cls(
            position_id=position.position_id,
            symbol=position.symbol,
            market=position.market,
            quantity=position.quantity,
            average_cost=position.average_cost,
            cost_basis=position.cost_basis,
            created_at=position.created_at,
            updated_at=position.updated_at,
        )


class PortfolioResponse(BaseModel):
    portfolio_id: UUID
    user_id: str
    name: str
    currency: Currency

    positions: list[PositionResponse]
    total_cost_basis: Decimal

    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(
        cls,
        portfolio: Portfolio,
    ) -> PortfolioResponse:
        return cls(
            portfolio_id=portfolio.portfolio_id,
            user_id=portfolio.user_id,
            name=portfolio.name,
            currency=portfolio.currency,
            positions=[
                PositionResponse.from_domain(
                    position
                )
                for position
                in portfolio.positions
            ],
            total_cost_basis=(
                portfolio.total_cost_basis
            ),
            created_at=portfolio.created_at,
            updated_at=portfolio.updated_at,
        )
