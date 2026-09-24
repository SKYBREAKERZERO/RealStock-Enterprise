from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest

from libs.domain.market import (
    Market,
)
from libs.domain.market import (
    MarketQuote as DomainMarketQuote,
)
from libs.trading.market import MarketQuote
from services.trading.cached_quote_provider import (
    CachedMarketQuoteProvider,
)


def build_domain_quote(
    *,
    symbol: str = "AAPL",
    market: Market = Market.US,
) -> DomainMarketQuote:
    return DomainMarketQuote(
        symbol=symbol,
        market=market,
        bid_price=Decimal("210.00"),
        ask_price=Decimal("212.00"),
        bid_size=100,
        ask_size=120,
        timestamp=datetime(
            2026,
            9,
            22,
            12,
            0,
            0,
            tzinfo=UTC,
        ),
    )


def test_cached_provider_returns_trading_quote() -> None:
    cache = Mock()

    cache.get_quote.return_value = (
        build_domain_quote()
    )

    provider = CachedMarketQuoteProvider(
        cache=cache,
    )

    quote = provider.get_quote(
        "AAPL"
    )

    assert quote == MarketQuote(
        symbol="AAPL",
        bid=Decimal("210.00"),
        ask=Decimal("212.00"),
    )

    cache.get_quote.assert_called_once_with(
        market=Market.US,
        symbol="AAPL",
    )


def test_cached_provider_normalizes_symbol() -> None:
    cache = Mock()

    cache.get_quote.return_value = (
        build_domain_quote()
    )

    provider = CachedMarketQuoteProvider(
        cache=cache,
    )

    quote = provider.get_quote(
        "  aapl  "
    )

    assert quote.symbol == "AAPL"

    cache.get_quote.assert_called_once_with(
        market=Market.US,
        symbol="AAPL",
    )


def test_cached_provider_rejects_empty_symbol() -> None:
    cache = Mock()

    provider = CachedMarketQuoteProvider(
        cache=cache,
    )

    with pytest.raises(
        ValueError,
        match="Symbol must not be empty",
    ):
        provider.get_quote("   ")

    cache.get_quote.assert_not_called()


def test_cached_provider_rejects_missing_quote() -> None:
    cache = Mock()

    cache.get_quote.return_value = None

    provider = CachedMarketQuoteProvider(
        cache=cache,
    )

    with pytest.raises(
        ValueError,
        match=(
            "No current bid/ask market quote "
            "available for AAPL"
        ),
    ):
        provider.get_quote(
            "AAPL"
        )


def test_cached_provider_rejects_wrong_symbol() -> None:
    cache = Mock()

    cache.get_quote.return_value = (
        build_domain_quote(
            symbol="MSFT",
        )
    )

    provider = CachedMarketQuoteProvider(
        cache=cache,
    )

    with pytest.raises(
        ValueError,
        match="unexpected symbol",
    ):
        provider.get_quote(
            "AAPL"
        )


def test_cached_provider_supports_configured_market() -> None:
    cache = Mock()

    cache.get_quote.return_value = (
        build_domain_quote(
            market=Market.US,
        )
    )

    provider = CachedMarketQuoteProvider(
        cache=cache,
        market=Market.US,
    )

    provider.get_quote(
        "AAPL"
    )

    cache.get_quote.assert_called_once_with(
        market=Market.US,
        symbol="AAPL",
    )