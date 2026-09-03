from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from libs.domain.market import (
    Market,
    MarketQuote,
    MarketTrade,
    TradeSide,
)
from services.market_ingestor.providers.mock import (
    DEFAULT_INSTRUMENTS,
    MockInstrument,
    MockMarketDataProvider,
)


pytestmark = pytest.mark.unit


# ============================================================
# MockInstrument
# ============================================================


def test_mock_instrument_can_be_created() -> None:
    instrument = MockInstrument(
        symbol="AAPL",
        market=Market.US,
        base_price=Decimal("229.50"),
    )

    assert instrument.symbol == "AAPL"
    assert instrument.market is Market.US
    assert (
        instrument.base_price
        == Decimal("229.50")
    )


def test_mock_instrument_normalizes_symbol() -> None:
    instrument = MockInstrument(
        symbol="  aapl  ",
        market=Market.US,
        base_price=Decimal("229.50"),
    )

    assert instrument.symbol == "AAPL"


def test_mock_instrument_rejects_empty_symbol() -> None:
    with pytest.raises(
        ValueError,
        match="symbol must not be empty",
    ):
        MockInstrument(
            symbol="   ",
            market=Market.US,
            base_price=Decimal("100"),
        )


def test_mock_instrument_rejects_zero_price() -> None:
    with pytest.raises(
        ValueError,
        match="base_price must be greater than zero",
    ):
        MockInstrument(
            symbol="AAPL",
            market=Market.US,
            base_price=Decimal("0"),
        )


def test_mock_instrument_rejects_negative_price() -> None:
    with pytest.raises(
        ValueError,
        match="base_price must be greater than zero",
    ):
        MockInstrument(
            symbol="AAPL",
            market=Market.US,
            base_price=Decimal("-1"),
        )


# ============================================================
# Provider configuration
# ============================================================


def test_default_instruments_are_available() -> None:
    assert DEFAULT_INSTRUMENTS

    symbols = {
        instrument.symbol
        for instrument in DEFAULT_INSTRUMENTS
    }

    assert "AAPL" in symbols
    assert "MSFT" in symbols
    assert "7203" in symbols


def test_provider_uses_default_instruments() -> None:
    provider = MockMarketDataProvider(
        seed=42,
    )

    assert provider.instruments
    assert (
        provider.instruments
        == DEFAULT_INSTRUMENTS
    )


def test_provider_accepts_custom_instruments() -> None:
    instrument = MockInstrument(
        symbol="TEST",
        market=Market.US,
        base_price=Decimal("100.00"),
    )

    provider = MockMarketDataProvider(
        instruments=[instrument],
        seed=42,
    )

    assert provider.instruments == (
        instrument,
    )


def test_provider_rejects_empty_instrument_list() -> None:
    with pytest.raises(
        ValueError,
        match="at least one instrument is required",
    ):
        MockMarketDataProvider(
            instruments=[],
        )


# ============================================================
# Trade generation
# ============================================================


def test_generate_trade_returns_domain_model() -> None:
    provider = MockMarketDataProvider(
        seed=42,
    )

    trade = provider.generate_trade()

    assert isinstance(
        trade,
        MarketTrade,
    )


def test_generate_trade_for_specific_instrument() -> None:
    instrument = MockInstrument(
        symbol="AAPL",
        market=Market.US,
        base_price=Decimal("229.50"),
    )

    provider = MockMarketDataProvider(
        instruments=[instrument],
        seed=42,
    )

    trade = provider.generate_trade(
        instrument=instrument,
    )

    assert trade.symbol == "AAPL"
    assert trade.market is Market.US


def test_generate_trade_has_positive_price() -> None:
    provider = MockMarketDataProvider(
        seed=42,
    )

    for _ in range(100):
        trade = provider.generate_trade()

        assert trade.price > Decimal("0")


def test_generate_trade_has_positive_quantity() -> None:
    provider = MockMarketDataProvider(
        seed=42,
    )

    for _ in range(100):
        trade = provider.generate_trade()

        assert trade.quantity > 0


def test_generate_trade_side_is_valid() -> None:
    provider = MockMarketDataProvider(
        seed=42,
    )

    for _ in range(100):
        trade = provider.generate_trade()

        assert trade.side in {
            TradeSide.BUY,
            TradeSide.SELL,
        }


def test_generate_trade_ids_are_unique() -> None:
    instrument = MockInstrument(
        symbol="AAPL",
        market=Market.US,
        base_price=Decimal("229.50"),
    )

    provider = MockMarketDataProvider(
        instruments=[instrument],
        seed=42,
    )

    trade_ids = {
        provider.generate_trade().trade_id
        for _ in range(100)
    }

    assert len(trade_ids) == 100


def test_trade_sequence_is_incrementing() -> None:
    instrument = MockInstrument(
        symbol="AAPL",
        market=Market.US,
        base_price=Decimal("229.50"),
    )

    provider = MockMarketDataProvider(
        instruments=[instrument],
        seed=42,
    )

    first = provider.generate_trade()
    second = provider.generate_trade()

    assert first.trade_id.endswith(
        "0000000001"
    )

    assert second.trade_id.endswith(
        "0000000002"
    )


def test_generate_trade_preserves_timestamp() -> None:
    timestamp = datetime(
        2026,
        9,
        3,
        12,
        0,
        0,
        tzinfo=timezone.utc,
    )

    provider = MockMarketDataProvider(
        seed=42,
    )

    trade = provider.generate_trade(
        timestamp=timestamp,
    )

    assert trade.timestamp == timestamp


# ============================================================
# Quote generation
# ============================================================


def test_generate_quote_returns_domain_model() -> None:
    provider = MockMarketDataProvider(
        seed=42,
    )

    quote = provider.generate_quote()

    assert isinstance(
        quote,
        MarketQuote,
    )


def test_generate_quote_for_specific_instrument() -> None:
    instrument = MockInstrument(
        symbol="MSFT",
        market=Market.US,
        base_price=Decimal("417.30"),
    )

    provider = MockMarketDataProvider(
        instruments=[instrument],
        seed=42,
    )

    quote = provider.generate_quote(
        instrument=instrument,
    )

    assert quote.symbol == "MSFT"
    assert quote.market is Market.US


def test_quote_bid_never_exceeds_ask() -> None:
    provider = MockMarketDataProvider(
        seed=42,
    )

    for _ in range(100):
        quote = provider.generate_quote()

        assert (
            quote.bid_price
            <= quote.ask_price
        )


def test_quote_prices_are_positive() -> None:
    provider = MockMarketDataProvider(
        seed=42,
    )

    for _ in range(100):
        quote = provider.generate_quote()

        assert (
            quote.bid_price
            > Decimal("0")
        )

        assert (
            quote.ask_price
            > Decimal("0")
        )


def test_quote_sizes_are_positive() -> None:
    provider = MockMarketDataProvider(
        seed=42,
    )

    for _ in range(100):
        quote = provider.generate_quote()

        assert quote.bid_size > 0
        assert quote.ask_size > 0


def test_generate_quote_preserves_timestamp() -> None:
    japan_timezone = timezone(
        timedelta(hours=9)
    )

    timestamp = datetime(
        2026,
        9,
        3,
        21,
        0,
        0,
        tzinfo=japan_timezone,
    )

    provider = MockMarketDataProvider(
        seed=42,
    )

    quote = provider.generate_quote(
        timestamp=timestamp,
    )

    # Domain model normalizes it to UTC.
    assert quote.timestamp == datetime(
        2026,
        9,
        3,
        12,
        0,
        0,
        tzinfo=timezone.utc,
    )


# ============================================================
# Deterministic generation
# ============================================================


def test_same_seed_generates_same_trade_sequence() -> None:
    instrument = MockInstrument(
        symbol="AAPL",
        market=Market.US,
        base_price=Decimal("229.50"),
    )

    provider_a = MockMarketDataProvider(
        instruments=[instrument],
        seed=12345,
    )

    provider_b = MockMarketDataProvider(
        instruments=[instrument],
        seed=12345,
    )

    for _ in range(20):
        trade_a = (
            provider_a.generate_trade()
        )

        trade_b = (
            provider_b.generate_trade()
        )

        assert (
            trade_a.symbol
            == trade_b.symbol
        )

        assert (
            trade_a.price
            == trade_b.price
        )

        assert (
            trade_a.quantity
            == trade_b.quantity
        )

        assert (
            trade_a.side
            == trade_b.side
        )

        assert (
            trade_a.trade_id
            == trade_b.trade_id
        )


def test_same_seed_generates_same_quote_sequence() -> None:
    instrument = MockInstrument(
        symbol="AAPL",
        market=Market.US,
        base_price=Decimal("229.50"),
    )

    provider_a = MockMarketDataProvider(
        instruments=[instrument],
        seed=54321,
    )

    provider_b = MockMarketDataProvider(
        instruments=[instrument],
        seed=54321,
    )

    for _ in range(20):
        quote_a = (
            provider_a.generate_quote()
        )

        quote_b = (
            provider_b.generate_quote()
        )

        assert (
            quote_a.symbol
            == quote_b.symbol
        )

        assert (
            quote_a.bid_price
            == quote_b.bid_price
        )

        assert (
            quote_a.ask_price
            == quote_b.ask_price
        )

        assert (
            quote_a.bid_size
            == quote_b.bid_size
        )

        assert (
            quote_a.ask_size
            == quote_b.ask_size
        )