from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from libs.domain.market import Market
from libs.domain.portfolio.exceptions import (
    DuplicatePositionError,
    InvalidPortfolioNameError,
    InvalidUserIdError,
)


class Currency(StrEnum):
    """
    Supported portfolio base currencies.
    """

    USD = "USD"
    JPY = "JPY"


class Position(BaseModel):
    """
    A financial position owned by a portfolio.

    Monetary and quantity values deliberately use Decimal rather
    than float to avoid binary floating-point precision errors.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    position_id: UUID = Field(
        default_factory=uuid4,
    )

    symbol: str
    market: Market

    quantity: Decimal = Field(
        gt=Decimal("0"),
    )

    average_cost: Decimal = Field(
        gt=Decimal("0"),
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(
            UTC
        )
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(
            UTC
        )
    )

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(
        cls,
        value: str,
    ) -> str:
        symbol = value.strip().upper()

        if not symbol:
            raise ValueError(
                "symbol must not be empty"
            )

        if len(symbol) > 32:
            raise ValueError(
                "symbol must not exceed 32 characters"
            )

        return symbol

    @field_validator(
        "created_at",
        "updated_at",
    )
    @classmethod
    def normalize_timestamp(
        cls,
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None:
            raise ValueError(
                "timestamp must be timezone-aware"
            )

        return value.astimezone(
            UTC
        )

    @property
    def cost_basis(self) -> Decimal:
        """
        Total acquisition cost of this position.

        quantity * average_cost
        """

        return (
            self.quantity
            * self.average_cost
        )

    @property
    def instrument_key(self) -> str:
        """
        Canonical identity used throughout RealStock.
        """

        return (
            f"{self.market.value}:"
            f"{self.symbol}"
        )


class Portfolio(BaseModel):
    """
    Portfolio aggregate root.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    portfolio_id: UUID = Field(
        default_factory=uuid4,
    )

    user_id: str
    name: str

    currency: Currency = Currency.USD

    positions: tuple[Position, ...] = ()

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(
            UTC
        )
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(
            UTC
        )
    )

    @field_validator("user_id")
    @classmethod
    def validate_user_id(
        cls,
        value: str,
    ) -> str:
        user_id = value.strip()

        if not user_id:
            raise InvalidUserIdError(
                "user_id must not be empty"
            )

        if len(user_id) > 128:
            raise InvalidUserIdError(
                "user_id must not exceed 128 characters"
            )

        return user_id

    @field_validator("name")
    @classmethod
    def validate_name(
        cls,
        value: str,
    ) -> str:
        name = value.strip()

        if not name:
            raise InvalidPortfolioNameError(
                "portfolio name must not be empty"
            )

        if len(name) > 100:
            raise InvalidPortfolioNameError(
                "portfolio name must not exceed 100 characters"
            )

        return name

    @field_validator(
        "created_at",
        "updated_at",
    )
    @classmethod
    def normalize_timestamp(
        cls,
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None:
            raise ValueError(
                "timestamp must be timezone-aware"
            )

        return value.astimezone(
            UTC
        )

    @model_validator(mode="after")
    def validate_unique_positions(
        self,
    ) -> Portfolio:
        seen: set[str] = set()

        for position in self.positions:
            key = position.instrument_key

            if key in seen:
                raise DuplicatePositionError(
                    f"duplicate position: {key}"
                )

            seen.add(key)

        return self

    @property
    def total_cost_basis(self) -> Decimal:
        """
        Sum acquisition cost across all positions.

        This is NOT current market value.
        """

        return sum(
            (
                position.cost_basis
                for position in self.positions
            ),
            start=Decimal("0"),
        )

    def get_position(
        self,
        *,
        market: Market,
        symbol: str,
    ) -> Position | None:
        normalized_symbol = (
            symbol.strip().upper()
        )

        for position in self.positions:
            if (
                position.market == market
                and position.symbol
                == normalized_symbol
            ):
                return position

        return None