from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from libs.trading.market import MarketQuote


class MarketQuoteProvider(Protocol):
    def get_quote(
        self,
        symbol: str,
    ) -> MarketQuote:
        """Return the latest normalized market quote."""


@dataclass(slots=True)
class QuoteService:
    provider: MarketQuoteProvider

    def get_quote(
        self,
        symbol: str,
    ) -> MarketQuote:
        normalized_symbol = self._normalize_symbol(symbol)

        quote = self.provider.get_quote(
            normalized_symbol
        )

        if quote.symbol != normalized_symbol:
            raise ValueError(
                "Market quote provider returned an unexpected symbol: "
                f"expected {normalized_symbol}, got {quote.symbol}."
            )

        return quote

    def _normalize_symbol(
        self,
        symbol: str,
    ) -> str:
        normalized_symbol = symbol.strip().upper()

        if not normalized_symbol:
            raise ValueError(
                "Symbol must not be empty."
            )

        return normalized_symbol


@dataclass(frozen=True, slots=True)
class RawQuote:
    symbol: str
    bid: Decimal
    ask: Decimal


class StaticQuoteProvider:
    """
    Temporary provider used for development and tests.

    This will later be replaced by an adapter around the
    project's real market-data provider.
    """

    def __init__(
        self,
        quotes: dict[str, RawQuote],
    ) -> None:
        self._quotes = {
            symbol.strip().upper(): quote
            for symbol, quote in quotes.items()
        }

    def get_quote(
        self,
        symbol: str,
    ) -> MarketQuote:
        normalized_symbol = symbol.strip().upper()

        try:
            raw_quote = self._quotes[
                normalized_symbol
            ]
        except KeyError as exc:
            raise ValueError(
                f"No market quote available for "
                f"{normalized_symbol}."
            ) from exc

        return MarketQuote(
            symbol=raw_quote.symbol,
            bid=raw_quote.bid,
            ask=raw_quote.ask,
        )