from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from libs.domain.market import MarketQuote


class SimulatedTradingQuoteRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    symbol: str = Field(min_length=1, max_length=32)
    bid_price: Decimal = Field(gt=Decimal("0"))
    ask_price: Decimal = Field(gt=Decimal("0"))
    bid_size: int = Field(default=100, ge=0)
    ask_size: int = Field(default=100, ge=0)
    ttl_seconds: int = Field(default=1800, ge=1, le=86400)

    @model_validator(mode="after")
    def validate_spread(self) -> SimulatedTradingQuoteRequest:
        if self.bid_price > self.ask_price:
            raise ValueError("bid_price must not exceed ask_price")
        return self


class SimulatedTradingQuoteResponse(BaseModel):
    symbol: str
    market: str
    bid_price: Decimal
    ask_price: Decimal
    bid_size: int
    ask_size: int
    timestamp: datetime

    @classmethod
    def from_domain(
        cls,
        quote: MarketQuote,
    ) -> SimulatedTradingQuoteResponse:
        return cls(
            symbol=quote.symbol,
            market=quote.market.value,
            bid_price=quote.bid_price,
            ask_price=quote.ask_price,
            bid_size=quote.bid_size,
            ask_size=quote.ask_size,
            timestamp=quote.timestamp,
        )
