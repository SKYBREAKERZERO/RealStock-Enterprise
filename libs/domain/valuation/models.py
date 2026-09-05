from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    model_validator,
)

from libs.domain.market import (
    Market,
    MarketQuote,
)
from libs.domain.portfolio import (
    Portfolio,
    Position,
)


class PositionValuation(BaseModel):
    """
    Current valuation of one portfolio position.

    Missing market data is represented explicitly with None.
    A missing quote must never be interpreted as a zero price.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

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
    def from_position(
        cls,
        *,
        position: Position,
        quote: MarketQuote | None,
    ) -> PositionValuation:
        if quote is None:
            return cls(
                position_id=position.position_id,
                symbol=position.symbol,
                market=position.market,
                quantity=position.quantity,
                average_cost=position.average_cost,
                cost_basis=position.cost_basis,
                market_price=None,
                market_value=None,
                unrealized_pnl=None,
                unrealized_pnl_percent=None,
                quote_timestamp=None,
                quote_available=False,
            )

        if (
            quote.market != position.market
            or quote.symbol != position.symbol
        ):
            raise ValueError(
                "quote instrument does not match position"
            )

        market_price = quote.mid_price

        market_value = (
            position.quantity
            * market_price
        )

        unrealized_pnl = (
            market_value
            - position.cost_basis
        )

        unrealized_pnl_percent = (
            unrealized_pnl
            / position.cost_basis
            * Decimal("100")
        )

        return cls(
            position_id=position.position_id,
            symbol=position.symbol,
            market=position.market,
            quantity=position.quantity,
            average_cost=position.average_cost,
            cost_basis=position.cost_basis,
            market_price=market_price,
            market_value=market_value,
            unrealized_pnl=unrealized_pnl,
            unrealized_pnl_percent=(
                unrealized_pnl_percent
            ),
            quote_timestamp=quote.timestamp,
            quote_available=True,
        )

    @model_validator(mode="after")
    def validate_quote_state(
        self,
    ) -> PositionValuation:
        quote_fields = (
            self.market_price,
            self.market_value,
            self.unrealized_pnl,
            self.unrealized_pnl_percent,
            self.quote_timestamp,
        )

        if self.quote_available:
            if any(
                value is None
                for value in quote_fields
            ):
                raise ValueError(
                    "priced position must contain "
                    "complete quote valuation data"
                )

        else:
            if any(
                value is not None
                for value in quote_fields
            ):
                raise ValueError(
                    "unpriced position must not contain "
                    "quote valuation data"
                )

        return self


class PortfolioValuation(BaseModel):
    """
    Current valuation snapshot for one portfolio.

    PnL totals only include positions that have valid quotes.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    portfolio_id: UUID

    total_cost_basis: Decimal

    priced_cost_basis: Decimal

    total_market_value: Decimal
    total_unrealized_pnl: Decimal

    priced_positions: int
    missing_quotes: int

    valuation_complete: bool

    positions: tuple[
        PositionValuation,
        ...
    ]

    @classmethod
    def from_positions(
        cls,
        *,
        portfolio: Portfolio,
        positions: tuple[
            PositionValuation,
            ...
        ],
    ) -> PortfolioValuation:
        priced = tuple(
            position
            for position in positions
            if position.quote_available
        )

        priced_cost_basis = sum(
            (
                position.cost_basis
                for position in priced
            ),
            start=Decimal("0"),
        )

        total_market_value = sum(
            (
                position.market_value
                for position in priced
                if position.market_value
                is not None
            ),
            start=Decimal("0"),
        )

        total_unrealized_pnl = sum(
            (
                position.unrealized_pnl
                for position in priced
                if position.unrealized_pnl
                is not None
            ),
            start=Decimal("0"),
        )

        priced_positions = len(priced)

        missing_quotes = (
            len(positions)
            - priced_positions
        )

        return cls(
            portfolio_id=portfolio.portfolio_id,
            total_cost_basis=(
                portfolio.total_cost_basis
            ),
            priced_cost_basis=(
                priced_cost_basis
            ),
            total_market_value=(
                total_market_value
            ),
            total_unrealized_pnl=(
                total_unrealized_pnl
            ),
            priced_positions=(
                priced_positions
            ),
            missing_quotes=(
                missing_quotes
            ),
            valuation_complete=(
                missing_quotes == 0
            ),
            positions=positions,
        )