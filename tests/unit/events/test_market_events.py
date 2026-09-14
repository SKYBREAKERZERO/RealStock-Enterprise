from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from libs.domain.market import (
    Market,
    MarketQuote,
    MarketTrade,
    TradeSide,
)
from libs.events.market import (
    MARKET_EVENT_SCHEMA_VERSION,
    MARKET_INGESTOR_SOURCE,
    MARKET_QUOTE_RECEIVED,
    MARKET_TRADE_RECEIVED,
    create_market_quote_event,
    create_market_trade_event,
)

pytestmark = pytest.mark.unit


def build_trade() -> MarketTrade:
    return MarketTrade(
        trade_id="trade-001",
        symbol="AAPL",
        market=Market.US,
        price=Decimal("229.51"),
        quantity=100,
        side=TradeSide.BUY,
        timestamp=datetime(
            2026,
            9,
            3,
            12,
            0,
            0,
            tzinfo=UTC,
        ),
    )


def build_quote() -> MarketQuote:
    return MarketQuote(
        symbol="AAPL",
        market=Market.US,
        bid_price=Decimal("229.50"),
        ask_price=Decimal("229.60"),
        bid_size=100,
        ask_size=120,
        timestamp=datetime(
            2026,
            9,
            3,
            12,
            0,
            1,
            tzinfo=UTC,
        ),
    )


# ============================================================
# Trade event
# ============================================================


def test_trade_domain_model_can_be_converted_to_event() -> None:
    trade = build_trade()

    event = create_market_trade_event(
        trade,
    )

    assert event.event_type == MARKET_TRADE_RECEIVED
    assert event.schema_version == MARKET_EVENT_SCHEMA_VERSION
    assert event.source == MARKET_INGESTOR_SOURCE
    assert event.occurred_at == trade.timestamp


def test_trade_event_payload_contains_domain_data() -> None:
    event = create_market_trade_event(
        build_trade(),
    )

    assert event.payload["trade_id"] == "trade-001"
    assert event.payload["symbol"] == "AAPL"
    assert event.payload["market"] == "US"
    assert event.payload["price"] == "229.51"
    assert event.payload["quantity"] == 100
    assert event.payload["side"] == "BUY"

    assert event.payload["timestamp"] == (
        "2026-09-03T12:00:00Z"
    )


def test_trade_event_is_valid_json() -> None:
    event = create_market_trade_event(
        build_trade(),
    )

    document = json.loads(
        event.to_event_json()
    )

    assert document["event_type"] == (
        "market.trade.received"
    )

    assert document["schema_version"] == 1

    assert document["payload"]["symbol"] == "AAPL"
    assert document["payload"]["price"] == "229.51"
    assert document["payload"]["quantity"] == 100


def test_trade_event_preserves_correlation_id() -> None:
    correlation_id = uuid4()

    event = create_market_trade_event(
        build_trade(),
        correlation_id=correlation_id,
    )

    assert event.correlation_id == correlation_id


def test_trade_event_preserves_causation_id() -> None:
    causation_id = uuid4()

    event = create_market_trade_event(
        build_trade(),
        causation_id=causation_id,
    )

    assert event.causation_id == causation_id


def test_trade_event_can_override_source() -> None:
    event = create_market_trade_event(
        build_trade(),
        source="market-provider-adapter",
    )

    assert event.source == "market-provider-adapter"


# ============================================================
# Quote event
# ============================================================


def test_quote_domain_model_can_be_converted_to_event() -> None:
    quote = build_quote()

    event = create_market_quote_event(
        quote,
    )

    assert event.event_type == MARKET_QUOTE_RECEIVED
    assert event.schema_version == MARKET_EVENT_SCHEMA_VERSION
    assert event.source == MARKET_INGESTOR_SOURCE
    assert event.occurred_at == quote.timestamp


def test_quote_event_payload_contains_domain_data() -> None:
    event = create_market_quote_event(
        build_quote(),
    )

    assert event.payload["symbol"] == "AAPL"
    assert event.payload["market"] == "US"

    assert event.payload["bid_price"] == "229.50"
    assert event.payload["ask_price"] == "229.60"

    assert event.payload["bid_size"] == 100
    assert event.payload["ask_size"] == 120

    assert event.payload["timestamp"] == (
        "2026-09-03T12:00:01Z"
    )


def test_quote_event_is_valid_json() -> None:
    event = create_market_quote_event(
        build_quote(),
    )

    document = json.loads(
        event.to_event_json()
    )

    assert document["event_type"] == (
        "market.quote.received"
    )

    assert document["schema_version"] == 1

    assert document["payload"]["symbol"] == "AAPL"
    assert document["payload"]["bid_price"] == "229.50"
    assert document["payload"]["ask_price"] == "229.60"


def test_quote_event_preserves_correlation_id() -> None:
    correlation_id = uuid4()

    event = create_market_quote_event(
        build_quote(),
        correlation_id=correlation_id,
    )

    assert event.correlation_id == correlation_id


def test_trade_and_quote_have_different_event_types() -> None:
    trade_event = create_market_trade_event(
        build_trade(),
    )

    quote_event = create_market_quote_event(
        build_quote(),
    )

    assert trade_event.event_type != quote_event.event_type

    assert trade_event.event_type == (
        "market.trade.received"
    )

    assert quote_event.event_type == (
        "market.quote.received"
    )