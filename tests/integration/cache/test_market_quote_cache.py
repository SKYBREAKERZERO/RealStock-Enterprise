from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from libs.cache import (
    MarketQuoteCache,
    get_redis_client,
)
from libs.domain.market import (
    Market,
    MarketQuote,
)


pytestmark = pytest.mark.integration

TEST_SYMBOL = "AAPL"


def build_quote() -> MarketQuote:
    return MarketQuote(
        symbol=TEST_SYMBOL,
        market=Market.US,
        bid_price=Decimal("200.10"),
        ask_price=Decimal("202.30"),
        bid_size=100,
        ask_size=120,
        timestamp=datetime(
            2026,
            9,
            5,
            0,
            0,
            0,
            tzinfo=timezone.utc,
        ),
    )


@pytest.fixture(autouse=True)
def cleanup_quote():
    cache = MarketQuoteCache()

    cache.delete_quote(
        market=Market.US,
        symbol=TEST_SYMBOL,
    )

    yield

    cache.delete_quote(
        market=Market.US,
        symbol=TEST_SYMBOL,
    )


def test_build_key_normalizes_symbol() -> None:
    key = MarketQuoteCache.build_key(
        market=Market.US,
        symbol="  aapl  ",
    )

    assert key == "realstock:quote:US:AAPL"


def test_set_and_get_quote() -> None:
    cache = MarketQuoteCache()

    quote = build_quote()

    cache.set_quote(quote)

    result = cache.get_quote(
        market=Market.US,
        symbol=TEST_SYMBOL,
    )

    assert result == quote


def test_get_quote_normalizes_symbol() -> None:
    cache = MarketQuoteCache()

    cache.set_quote(
        build_quote()
    )

    result = cache.get_quote(
        market=Market.US,
        symbol="  aapl  ",
    )

    assert result is not None
    assert result.symbol == "AAPL"


def test_decimal_precision_round_trip() -> None:
    cache = MarketQuoteCache()

    cache.set_quote(
        build_quote()
    )

    result = cache.get_quote(
        market=Market.US,
        symbol=TEST_SYMBOL,
    )

    assert result is not None

    assert (
        result.bid_price
        == Decimal("200.10")
    )

    assert (
        result.ask_price
        == Decimal("202.30")
    )

    assert (
        result.mid_price
        == Decimal("201.20")
    )


def test_timestamp_round_trip() -> None:
    cache = MarketQuoteCache()

    quote = build_quote()

    cache.set_quote(quote)

    result = cache.get_quote(
        market=Market.US,
        symbol=TEST_SYMBOL,
    )

    assert result is not None
    assert result.timestamp == quote.timestamp
    assert result.timestamp.tzinfo is not None


def test_quote_has_ttl() -> None:
    cache = MarketQuoteCache(
        ttl_seconds=30,
    )

    cache.set_quote(
        build_quote()
    )

    redis_client = get_redis_client()

    key = cache.build_key(
        market=Market.US,
        symbol=TEST_SYMBOL,
    )

    ttl = redis_client.ttl(key)

    assert 0 < ttl <= 30


def test_missing_quote_returns_none() -> None:
    cache = MarketQuoteCache()

    result = cache.get_quote(
        market=Market.US,
        symbol=TEST_SYMBOL,
    )

    assert result is None


def test_delete_quote() -> None:
    cache = MarketQuoteCache()

    cache.set_quote(
        build_quote()
    )

    deleted = cache.delete_quote(
        market=Market.US,
        symbol=TEST_SYMBOL,
    )

    assert deleted is True

    assert (
        cache.get_quote(
            market=Market.US,
            symbol=TEST_SYMBOL,
        )
        is None
    )


def test_rejects_invalid_ttl() -> None:
    with pytest.raises(
        ValueError,
        match="ttl_seconds must be greater than zero",
    ):
        MarketQuoteCache(
            ttl_seconds=0,
        )