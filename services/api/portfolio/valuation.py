from __future__ import annotations

from libs.cache import MarketQuoteCache
from libs.domain.portfolio import (
    Portfolio,
    Position,
)
from libs.domain.valuation import (
    PortfolioValuation,
    PositionValuation,
)
from services.api.portfolio.valuation_price import (
    ValuationInstrument,
    ValuationPrice,
    ValuationPriceSource,
)


class PortfolioValuationService:
    """
    Application service responsible for producing a current
    portfolio valuation.

    Two price paths are intentionally supported:

    Legacy:
        MarketQuoteCache
        -> bid/ask MarketQuote
        -> midpoint

    Snapshot:
        ValuationPriceSource
        -> explicit valuation price
        -> Twelve Data close in the current runtime adapter

    The snapshot path does not fabricate bid/ask semantics.
    """

    def __init__(
        self,
        quote_cache: (
            MarketQuoteCache
            | None
        ) = None,
        *,
        price_source: (
            ValuationPriceSource
            | None
        ) = None,
    ) -> None:
        if (
            quote_cache is not None
            and price_source is not None
        ):
            raise ValueError(
                "quote_cache and price_source "
                "cannot both be configured"
            )

        self._price_source = (
            price_source
        )

        if price_source is None:
            self._quote_cache = (
                quote_cache
                if quote_cache
                is not None
                else MarketQuoteCache()
            )

        else:
            self._quote_cache = None

    def value_portfolio(
        self,
        *,
        portfolio: Portfolio,
    ) -> PortfolioValuation:
        if self._price_source is None:
            position_valuations = (
                tuple(
                    self
                    ._value_position_from_quote(
                        position=position,
                    )
                    for position
                    in portfolio.positions
                )
            )

        else:
            position_valuations = (
                self
                ._value_positions_from_prices(
                    portfolio=portfolio,
                )
            )

        return (
            PortfolioValuation
            .from_positions(
                portfolio=portfolio,
                positions=(
                    position_valuations
                ),
            )
        )

    def _value_positions_from_prices(
        self,
        *,
        portfolio: Portfolio,
    ) -> tuple[
        PositionValuation,
        ...
    ]:
        if not portfolio.positions:
            return ()

        if self._price_source is None:
            raise RuntimeError(
                "valuation price source "
                "is not configured"
            )

        instruments = tuple(
            ValuationInstrument(
                market=position.market,
                symbol=position.symbol,
            )
            for position
            in portfolio.positions
        )

        prices = (
            self._price_source
            .get_prices(
                instruments
            )
        )

        return tuple(
            self
            ._value_position_from_price(
                position=position,
                valuation_price=(
                    prices.get(
                        (
                            position.market,
                            position.symbol,
                        )
                    )
                ),
            )
            for position
            in portfolio.positions
        )

    def _value_position_from_quote(
        self,
        *,
        position: Position,
    ) -> PositionValuation:
        if self._quote_cache is None:
            raise RuntimeError(
                "market quote cache "
                "is not configured"
            )

        quote = (
            self._quote_cache
            .get_quote(
                market=position.market,
                symbol=position.symbol,
            )
        )

        return (
            PositionValuation
            .from_position(
                position=position,
                quote=quote,
            )
        )

    @staticmethod
    def _value_position_from_price(
        *,
        position: Position,
        valuation_price: (
            ValuationPrice
            | None
        ),
    ) -> PositionValuation:
        if valuation_price is None:
            return (
                PositionValuation
                .from_market_price(
                    position=position,
                    market_price=None,
                    quote_timestamp=None,
                )
            )

        if (
            valuation_price.market
            != position.market
            or valuation_price.symbol
            != position.symbol
        ):
            raise ValueError(
                "valuation price instrument "
                "does not match position"
            )

        return (
            PositionValuation
            .from_market_price(
                position=position,
                market_price=(
                    valuation_price.price
                ),
                quote_timestamp=(
                    valuation_price
                    .timestamp
                ),
            )
        )