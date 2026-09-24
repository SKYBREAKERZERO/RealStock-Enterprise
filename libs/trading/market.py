from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class MarketQuote:
    symbol: str
    bid: Decimal
    ask: Decimal

    def __post_init__(self) -> None:
        normalized_symbol = self.symbol.strip().upper()

        if not normalized_symbol:
            raise ValueError("Symbol must not be empty.")

        if self.bid <= ZERO:
            raise ValueError("Bid must be greater than zero.")

        if self.ask <= ZERO:
            raise ValueError("Ask must be greater than zero.")

        if self.ask < self.bid:
            raise ValueError("Ask must not be lower than bid.")

        object.__setattr__(self, "symbol", normalized_symbol)