from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from libs.domain.market import (
    InvalidPriceError,
    InvalidSymbolError,
    InvalidTimestampError,
    Market,
    MarketQuote,
    MarketTrade,
    TradeSide,
)

pytestmark = pytest.mark.unit


# ============================================================
# Helpers
# ============================================================


def utc_now() -> datetime:
    return datetime.now(UTC)


def build_trade(**overrides: object) -> MarketTrade:
    data: dict[str, object] = {
        "trade_id": "trade-001",
        "symbol": "AAPL",
        "market": Market.US,
        "price": Decimal("229.51"),
        "quantity": 100,
        "side": TradeSide.BUY,
        "timestamp": utc_now(),
    }

    data.update(overrides)

    return MarketTrade(**data)


def build_quote(**overrides: object) -> MarketQuote:
    data: dict[str, object] = {
        "symbol": "AAPL",
        "market": Market.US,
        "bid_price": Decimal("229.50"),
        "ask_price": Decimal("229.60"),
        "bid_size": 100,
        "ask_size": 120,
        "timestamp": utc_now(),
    }

    data.update(overrides)

    return MarketQuote(**data)


# ============================================================
# MarketTrade
# ============================================================


def test_trade_can_be_created() -> None:
    trade = build_trade()

    assert trade.trade_id == "trade-001"
    assert trade.symbol == "AAPL"
    assert trade.market is Market.US
    assert trade.price == Decimal("229.51")
    assert trade.quantity == 100
    assert trade.side is TradeSide.BUY


def test_trade_symbol_is_normalized_to_uppercase() -> None:
    trade = build_trade(
        symbol="  aapl  ",
    )

    assert trade.symbol == "AAPL"


def test_trade_notional_is_calculated_correctly() -> None:
    trade = build_trade(
        price=Decimal("229.51"),
        quantity=100,
    )

    assert trade.notional == Decimal("22951.00")


def test_trade_rejects_empty_trade_id() -> None:
    with pytest.raises(
        ValueError,
        match="trade_id must not be empty",
    ):
        build_trade(
            trade_id="   ",
        )


def test_trade_rejects_empty_symbol() -> None:
    with pytest.raises(
        InvalidSymbolError,
        match="symbol must not be empty",
    ):
        build_trade(
            symbol="   ",
        )


def test_trade_rejects_symbol_longer_than_32_characters() -> None:
    with pytest.raises(
        InvalidSymbolError,
        match="symbol must not exceed 32 characters",
    ):
        build_trade(
            symbol="A" * 33,
        )


def test_trade_rejects_zero_price() -> None:
    with pytest.raises(ValidationError):
        build_trade(
            price=Decimal("0"),
        )


def test_trade_rejects_negative_price() -> None:
    with pytest.raises(ValidationError):
        build_trade(
            price=Decimal("-1"),
        )


def test_trade_rejects_zero_quantity() -> None:
    with pytest.raises(ValidationError):
        build_trade(
            quantity=0,
        )


def test_trade_rejects_negative_quantity() -> None:
    with pytest.raises(ValidationError):
        build_trade(
            quantity=-1,
        )


def test_trade_rejects_naive_timestamp() -> None:
    naive_timestamp = datetime(
        2026,
        9,
        3,
        12,
        0,
        0,
    )

    with pytest.raises(
        InvalidTimestampError,
        match="timestamp must be timezone-aware",
    ):
        build_trade(
            timestamp=naive_timestamp,
        )


def test_trade_timestamp_is_normalized_to_utc() -> None:
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

    trade = build_trade(
        timestamp=timestamp,
    )

    assert trade.timestamp.tzinfo == UTC

    assert trade.timestamp == datetime(
        2026,
        9,
        3,
        12,
        0,
        0,
        tzinfo=UTC,
    )


def test_trade_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        build_trade(
            unexpected_field="not-allowed",
        )


def test_trade_is_immutable() -> None:
    trade = build_trade()

    with pytest.raises(ValidationError):
        trade.quantity = 200  # type: ignore[misc]


# ============================================================
# MarketQuote
# ============================================================


def test_quote_can_be_created() -> None:
    quote = build_quote()

    assert quote.symbol == "AAPL"
    assert quote.market is Market.US
    assert quote.bid_price == Decimal("229.50")
    assert quote.ask_price == Decimal("229.60")
    assert quote.bid_size == 100
    assert quote.ask_size == 120


def test_quote_symbol_is_normalized_to_uppercase() -> None:
    quote = build_quote(
        symbol="  msft  ",
    )

    assert quote.symbol == "MSFT"


def test_quote_mid_price_is_calculated_correctly() -> None:
    quote = build_quote(
        bid_price=Decimal("229.50"),
        ask_price=Decimal("229.60"),
    )

    assert quote.mid_price == Decimal("229.55")


def test_quote_spread_is_calculated_correctly() -> None:
    quote = build_quote(
        bid_price=Decimal("229.50"),
        ask_price=Decimal("229.60"),
    )

    assert quote.spread == Decimal("0.10")


def test_quote_allows_equal_bid_and_ask_price() -> None:
    quote = build_quote(
        bid_price=Decimal("100.00"),
        ask_price=Decimal("100.00"),
    )

    assert quote.spread == Decimal("0.00")
    assert quote.mid_price == Decimal("100.00")


def test_quote_rejects_bid_price_above_ask_price() -> None:
    with pytest.raises(
        InvalidPriceError,
        match="bid_price must not exceed ask_price",
    ):
        build_quote(
            bid_price=Decimal("230.00"),
            ask_price=Decimal("229.00"),
        )


def test_quote_rejects_zero_bid_price() -> None:
    with pytest.raises(ValidationError):
        build_quote(
            bid_price=Decimal("0"),
        )


def test_quote_rejects_zero_ask_price() -> None:
    with pytest.raises(ValidationError):
        build_quote(
            ask_price=Decimal("0"),
        )


def test_quote_rejects_negative_bid_size() -> None:
    with pytest.raises(ValidationError):
        build_quote(
            bid_size=-1,
        )


def test_quote_rejects_negative_ask_size() -> None:
    with pytest.raises(ValidationError):
        build_quote(
            ask_size=-1,
        )


def test_quote_rejects_naive_timestamp() -> None:
    naive_timestamp = datetime(
        2026,
        9,
        3,
        12,
        0,
        0,
    )

    with pytest.raises(
        InvalidTimestampError,
        match="timestamp must be timezone-aware",
    ):
        build_quote(
            timestamp=naive_timestamp,
        )


def test_quote_is_immutable() -> None:
    quote = build_quote()

    with pytest.raises(ValidationError):
        quote.bid_price = Decimal("100")  # type: ignore[misc]


# ============================================================
# Enum validation
# ============================================================


def test_trade_rejects_unsupported_market() -> None:
    with pytest.raises(ValidationError):
        build_trade(
            market="CN",
        )


def test_trade_rejects_invalid_side() -> None:
    with pytest.raises(ValidationError):
        build_trade(
            side="HOLD",
        )