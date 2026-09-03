from __future__ import annotations

from abc import ABC, abstractmethod

from libs.domain.market import (
    MarketQuote,
    MarketTrade,
)


class MarketDataProvider(ABC):
    @abstractmethod
    def get_trade(
        self,
        symbol: str,
    ) -> MarketTrade:
        raise NotImplementedError

    @abstractmethod
    def get_quote(
        self,
        symbol: str,
    ) -> MarketQuote:
        raise NotImplementedError