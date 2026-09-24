from __future__ import annotations

from dataclasses import dataclass

from libs.cache import MarketQuoteCache
from libs.domain.market import Market
from libs.trading.market import MarketQuote


@dataclass(slots=True)
class CachedMarketQuoteProvider:
    """
    Trading quote provider backed by the existing Redis
    MarketQuoteCache.

    The cache stores the application's canonical domain
    bid/ask quote. This adapter converts that quote into
    the smaller trading-domain MarketQuote required by
    PaperBroker.

    No synthetic bid/ask values are created here.
    """

    cache: MarketQuoteCache
    market: Market = Market.US

    def get_quote(
        self,
        symbol: str,
    ) -> MarketQuote:
        normalized_symbol = self._normalize_symbol(
            symbol
        )

        cached_quote = self.cache.get_quote(
            market=self.market,
            symbol=normalized_symbol,
        )

        if cached_quote is None:
            raise ValueError(
                "No current bid/ask market quote "
                f"available for {normalized_symbol}."
            )

        if cached_quote.symbol != normalized_symbol:
            raise ValueError(
                "Cached market quote returned an "
                "unexpected symbol: "
                f"expected {normalized_symbol}, "
                f"got {cached_quote.symbol}."
            )

        if cached_quote.market != self.market:
            raise ValueError(
                "Cached market quote returned an "
                "unexpected market: "
                f"expected {self.market.value}, "
                f"got {cached_quote.market.value}."
            )

        return MarketQuote(
            symbol=cached_quote.symbol,
            bid=cached_quote.bid_price,
            ask=cached_quote.ask_price,
        )

    @staticmethod
    def _normalize_symbol(
        symbol: str,
    ) -> str:
        normalized_symbol = symbol.strip().upper()

        if not normalized_symbol:
            raise ValueError(
                "Symbol must not be empty."
            )

        return normalized_symbol