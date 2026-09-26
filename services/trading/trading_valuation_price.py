from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from libs.cache import MarketQuoteCache
from libs.domain.market import Market
from services.api.portfolio.valuation import ValuationInstrument
from services.api.portfolio.valuation_price import (
    BatchMarketValuationPriceSource,
)

TWO = Decimal("2")
ZERO = Decimal("0")


@dataclass(slots=True)
class CachedTradingValuationPriceSource:
    """
    Legacy/local paper-trading valuation adapter.

    The cache already stores a real bid/ask MarketQuote.
    The valuation policy for this path is the bid/ask midpoint.
    """

    quote_cache: MarketQuoteCache
    market: Market = Market.US

    def get_prices(
        self,
        symbols: list[str],
    ) -> dict[str, Decimal]:
        prices: dict[str, Decimal] = {}

        for raw_symbol in symbols:
            symbol = raw_symbol.strip().upper()

            if not symbol:
                continue

            quote = self.quote_cache.get_quote(
                market=self.market,
                symbol=symbol,
            )

            if quote is None:
                continue

            mark_price = (
                quote.bid + quote.ask
            ) / TWO

            if mark_price <= ZERO:
                continue

            prices[symbol] = mark_price

        return prices


@dataclass(slots=True)
class BatchTradingValuationPriceSource:
    """
    Adapter from the existing portfolio OHLC valuation source to the
    symbol-only paper-trading valuation boundary.

    Paper trading currently stores symbols without a market column,
    so the current US-market assumption is explicit here.

    Twelve Data snapshot close remains the valuation price through
    BatchMarketValuationPriceSource. It is never converted into
    synthetic bid/ask data.
    """

    price_source: BatchMarketValuationPriceSource
    market: Market = Market.US

    def get_prices(
        self,
        symbols: list[str],
    ) -> dict[str, Decimal]:
        normalized_symbols = [
            symbol.strip().upper()
            for symbol in symbols
            if symbol.strip()
        ]

        if not normalized_symbols:
            return {}

        instruments = tuple(
            ValuationInstrument(
                market=self.market,
                symbol=symbol,
            )
            for symbol in normalized_symbols
        )

        valuation_prices = (
            self.price_source.get_prices(
                instruments
            )
        )

        prices: dict[str, Decimal] = {}

        for symbol in normalized_symbols:
            valuation_price = (
                valuation_prices.get(
                    (
                        self.market,
                        symbol,
                    )
                )
            )

            if valuation_price is None:
                continue

            if valuation_price.price <= ZERO:
                continue

            prices[symbol] = (
                valuation_price.price
            )

        return prices
