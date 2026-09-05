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


class PortfolioValuationService:
    """
    Application service responsible for producing a current
    portfolio valuation from the latest market quote cache.

    Responsibilities:
    - Read latest quotes for portfolio positions.
    - Build PositionValuation objects.
    - Aggregate them into PortfolioValuation.

    This service does not persist portfolio state and does not
    own a database transaction.
    """

    def __init__(
        self,
        quote_cache: MarketQuoteCache | None = None,
    ) -> None:
        self._quote_cache = (
            quote_cache
            if quote_cache is not None
            else MarketQuoteCache()
        )

    def value_portfolio(
        self,
        *,
        portfolio: Portfolio,
    ) -> PortfolioValuation:
        position_valuations = tuple(
            self._value_position(
                position=position,
            )
            for position in portfolio.positions
        )

        return PortfolioValuation.from_positions(
            portfolio=portfolio,
            positions=position_valuations,
        )

    def _value_position(
        self,
        *,
        position: Position,
    ) -> PositionValuation:
        quote = self._quote_cache.get_quote(
            market=position.market,
            symbol=position.symbol,
        )

        return PositionValuation.from_position(
            position=position,
            quote=quote,
        )