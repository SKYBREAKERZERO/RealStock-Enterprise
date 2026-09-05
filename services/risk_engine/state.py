from __future__ import annotations

from typing import Protocol

from libs.domain.market import (
    Market,
    MarketQuote,
)


class QuoteStateStore(Protocol):
    """
    State abstraction used by the risk engine.

    Production implementations may use Flink keyed state,
    Redis, DynamoDB, or another state backend.
    """

    def get_quote(
        self,
        *,
        market: Market,
        symbol: str,
    ) -> MarketQuote | None:
        ...

    def set_quote(
        self,
        quote: MarketQuote,
    ) -> None:
        ...


class InMemoryQuoteStateStore:
    """
    Deterministic in-memory implementation used for local
    execution and unit tests.

    This is processing state, not the same thing as the
    latest-quote cache used by the Portfolio API.
    """

    def __init__(self) -> None:
        self._quotes: dict[
            str,
            MarketQuote,
        ] = {}

    @staticmethod
    def build_key(
        *,
        market: Market,
        symbol: str,
    ) -> str:
        normalized_symbol = (
            symbol.strip().upper()
        )

        if not normalized_symbol:
            raise ValueError(
                "symbol must not be empty"
            )

        return (
            f"{market.value}:"
            f"{normalized_symbol}"
        )

    def get_quote(
        self,
        *,
        market: Market,
        symbol: str,
    ) -> MarketQuote | None:
        key = self.build_key(
            market=market,
            symbol=symbol,
        )

        return self._quotes.get(
            key
        )

    def set_quote(
        self,
        quote: MarketQuote,
    ) -> None:
        key = self.build_key(
            market=quote.market,
            symbol=quote.symbol,
        )

        self._quotes[key] = quote