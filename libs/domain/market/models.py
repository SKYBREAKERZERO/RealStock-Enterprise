from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from libs.domain.market.exceptions import (
    InvalidPriceError,
    InvalidQuantityError,
    InvalidSymbolError,
    InvalidTimestampError,
)


class Market(StrEnum):
    """
    Supported financial markets.
    """

    US = "US"
    JP = "JP"


class TradeSide(StrEnum):
    """
    Trade direction.
    """

    BUY = "BUY"
    SELL = "SELL"


class MarketQuote(BaseModel):
    """
    Latest quote for a financial instrument.

    This is a domain model and intentionally contains no AWS,
    database, FastAPI, or transport-specific dependencies.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    symbol: str
    market: Market

    bid_price: Decimal = Field(
        gt=Decimal("0"),
    )

    ask_price: Decimal = Field(
        gt=Decimal("0"),
    )

    bid_size: int = Field(
        ge=0,
    )

    ask_size: int = Field(
        ge=0,
    )

    timestamp: datetime

    @field_validator("symbol")
    @classmethod
    def validate_symbol(
        cls,
        value: str,
    ) -> str:
        symbol = value.strip().upper()

        if not symbol:
            raise InvalidSymbolError(
                "symbol must not be empty"
            )

        if len(symbol) > 32:
            raise InvalidSymbolError(
                "symbol must not exceed 32 characters"
            )

        return symbol

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(
        cls,
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None:
            raise InvalidTimestampError(
                "timestamp must be timezone-aware"
            )

        return value.astimezone(
            timezone.utc
        )

    @model_validator(mode="after")
    def validate_spread(
        self,
    ) -> MarketQuote:
        if self.bid_price > self.ask_price:
            raise InvalidPriceError(
                "bid_price must not exceed ask_price"
            )

        return self

    @property
    def mid_price(self) -> Decimal:
        return (
            self.bid_price
            + self.ask_price
        ) / Decimal("2")

    @property
    def spread(self) -> Decimal:
        return (
            self.ask_price
            - self.bid_price
        )


class MarketTrade(BaseModel):
    """
    Executed market trade.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    trade_id: str

    symbol: str
    market: Market

    price: Decimal = Field(
        gt=Decimal("0"),
    )

    quantity: int = Field(
        gt=0,
    )

    side: TradeSide

    timestamp: datetime

    @field_validator("trade_id")
    @classmethod
    def validate_trade_id(
        cls,
        value: str,
    ) -> str:
        trade_id = value.strip()

        if not trade_id:
            raise ValueError(
                "trade_id must not be empty"
            )

        return trade_id

    @field_validator("symbol")
    @classmethod
    def validate_symbol(
        cls,
        value: str,
    ) -> str:
        symbol = value.strip().upper()

        if not symbol:
            raise InvalidSymbolError(
                "symbol must not be empty"
            )

        if len(symbol) > 32:
            raise InvalidSymbolError(
                "symbol must not exceed 32 characters"
            )

        return symbol

    @field_validator("price")
    @classmethod
    def validate_price(
        cls,
        value: Decimal,
    ) -> Decimal:
        if value <= 0:
            raise InvalidPriceError(
                "price must be greater than zero"
            )

        return value

    @field_validator("quantity")
    @classmethod
    def validate_quantity(
        cls,
        value: int,
    ) -> int:
        if value <= 0:
            raise InvalidQuantityError(
                "quantity must be greater than zero"
            )

        return value

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(
        cls,
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None:
            raise InvalidTimestampError(
                "timestamp must be timezone-aware"
            )

        return value.astimezone(
            timezone.utc
        )

    @property
    def notional(self) -> Decimal:
        return (
            self.price
            * Decimal(self.quantity)
        )