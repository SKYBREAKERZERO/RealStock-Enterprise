from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

from libs.domain.market import Market
from libs.trading.market import MarketQuote
from services.trading.trading_valuation_price import (
    BatchTradingValuationPriceSource,
    CachedTradingValuationPriceSource,
)


def test_cached_source_uses_bid_ask_midpoint() -> None:
    quote_cache = Mock()

    quote_cache.get_quote.return_value = (
        MarketQuote(
            symbol="AAPL",
            bid=Decimal("209"),
            ask=Decimal("211"),
        )
    )

    source = CachedTradingValuationPriceSource(
        quote_cache=quote_cache,
    )

    prices = source.get_prices(
        [
            "aapl",
        ]
    )

    assert prices == {
        "AAPL": Decimal("210"),
    }

    quote_cache.get_quote.assert_called_once_with(
        market=Market.US,
        symbol="AAPL",
    )


def test_cached_source_skips_missing_quote() -> None:
    quote_cache = Mock()

    quote_cache.get_quote.return_value = None

    source = CachedTradingValuationPriceSource(
        quote_cache=quote_cache,
    )

    assert (
        source.get_prices(
            [
                "AAPL",
            ]
        )
        == {}
    )


def test_batch_source_converts_close_valuation_price() -> None:
    price_source = Mock()

    price_source.get_prices.return_value = {
        (
            Market.US,
            "AAPL",
        ): SimpleNamespace(
            price=Decimal("210"),
        ),
    }

    source = BatchTradingValuationPriceSource(
        price_source=price_source,
    )

    prices = source.get_prices(
        [
            "aapl",
        ]
    )

    assert prices == {
        "AAPL": Decimal("210"),
    }

    instruments = (
        price_source
        .get_prices
        .call_args
        .args[0]
    )

    assert len(instruments) == 1
    assert instruments[0].market == Market.US
    assert instruments[0].symbol == "AAPL"


def test_batch_source_skips_missing_price() -> None:
    price_source = Mock()
    price_source.get_prices.return_value = {}

    source = BatchTradingValuationPriceSource(
        price_source=price_source,
    )

    assert (
        source.get_prices(
            [
                "AAPL",
            ]
        )
        == {}
    )
