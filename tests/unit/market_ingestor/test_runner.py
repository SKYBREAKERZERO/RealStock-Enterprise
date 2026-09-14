from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from libs.domain.market import (
    Market,
    MarketQuote,
    MarketTrade,
    TradeSide,
)
from libs.events.envelope import EventEnvelope
from services.market_ingestor.providers.mock import (
    MockInstrument,
    MockMarketDataProvider,
)
from services.market_ingestor.runner import (
    MarketIngestorRunner,
    RunnerConfig,
    create_quote_event,
    create_trade_event,
)

pytestmark = pytest.mark.unit


# ============================================================
# Test constants
# ============================================================

STREAM_NAME = "realstock-market-events-local"

TEST_TIMESTAMP = datetime(
    2026,
    9,
    3,
    12,
    0,
    0,
    tzinfo=UTC,
)


# ============================================================
# Test doubles
# ============================================================


@dataclass(
    frozen=True,
    slots=True,
)
class FakePublishResult:
    """
    Minimal producer result required by MarketIngestorRunner.
    """

    shard_id: str = "shardId-000000000000"
    sequence_number: str = "1"


@dataclass(
    frozen=True,
    slots=True,
)
class RecordedPublish:
    """
    One call received by FakeProducer.
    """

    event: EventEnvelope[Any]
    partition_key: str


class FakeProducer:
    """
    In-memory replacement for KinesisMarketEventProducer.

    No LocalStack or AWS call is performed.
    """

    def __init__(self) -> None:
        self.published: list[
            RecordedPublish
        ] = []

    def publish(
        self,
        *,
        event: EventEnvelope[Any],
        partition_key: str,
    ) -> FakePublishResult:
        self.published.append(
            RecordedPublish(
                event=event,
                partition_key=partition_key,
            )
        )

        return FakePublishResult()


# ============================================================
# Helpers
# ============================================================


def build_instrument() -> MockInstrument:
    return MockInstrument(
        symbol="AAPL",
        market=Market.US,
        base_price=Decimal("229.50"),
    )


def build_provider(
    *,
    seed: int = 42,
) -> MockMarketDataProvider:
    instrument = build_instrument()

    return MockMarketDataProvider(
        instruments=[
            instrument,
        ],
        seed=seed,
    )


def build_runner(
    *,
    mode: str = "both",
    max_events: int | None = None,
    interval_seconds: float = 0,
    seed: int = 42,
) -> tuple[
    MarketIngestorRunner,
    FakeProducer,
]:
    config = RunnerConfig(
        stream_name=STREAM_NAME,
        mode=mode,  # type: ignore[arg-type]
        interval_seconds=interval_seconds,
        max_events=max_events,
        seed=seed,
    )

    provider = build_provider(
        seed=seed,
    )

    producer = FakeProducer()

    runner = MarketIngestorRunner(
        config=config,
        provider=provider,
        producer=producer,  # type: ignore[arg-type]
    )

    return (
        runner,
        producer,
    )


# ============================================================
# RunnerConfig
# ============================================================


def test_runner_config_can_be_created() -> None:
    config = RunnerConfig(
        stream_name=STREAM_NAME,
        mode="both",
        interval_seconds=1.0,
        max_events=10,
        seed=42,
    )

    assert (
        config.stream_name
        == STREAM_NAME
    )

    assert config.mode == "both"

    assert (
        config.interval_seconds
        == 1.0
    )

    assert config.max_events == 10

    assert config.seed == 42


def test_runner_config_allows_zero_interval() -> None:
    config = RunnerConfig(
        stream_name=STREAM_NAME,
        mode="trade",
        interval_seconds=0,
        max_events=1,
        seed=None,
    )

    assert (
        config.interval_seconds
        == 0
    )


def test_runner_config_rejects_empty_stream_name() -> None:
    with pytest.raises(
        ValueError,
        match="stream_name must not be empty",
    ):
        RunnerConfig(
            stream_name="   ",
            mode="both",
            interval_seconds=1,
            max_events=None,
            seed=None,
        )


def test_runner_config_rejects_negative_interval() -> None:
    with pytest.raises(
        ValueError,
        match="interval_seconds must be >= 0",
    ):
        RunnerConfig(
            stream_name=STREAM_NAME,
            mode="both",
            interval_seconds=-1,
            max_events=None,
            seed=None,
        )


def test_runner_config_rejects_zero_max_events() -> None:
    with pytest.raises(
        ValueError,
        match="max_events must be greater than zero",
    ):
        RunnerConfig(
            stream_name=STREAM_NAME,
            mode="both",
            interval_seconds=0,
            max_events=0,
            seed=None,
        )


def test_runner_config_rejects_negative_max_events() -> None:
    with pytest.raises(
        ValueError,
        match="max_events must be greater than zero",
    ):
        RunnerConfig(
            stream_name=STREAM_NAME,
            mode="both",
            interval_seconds=0,
            max_events=-1,
            seed=None,
        )


# ============================================================
# Trade event factory
# ============================================================


def test_create_trade_event() -> None:
    trade = MarketTrade(
        trade_id="trade-001",
        symbol="AAPL",
        market=Market.US,
        price=Decimal("229.51"),
        quantity=100,
        side=TradeSide.BUY,
        timestamp=TEST_TIMESTAMP,
    )

    event = create_trade_event(
        trade
    )

    assert (
        event.event_type
        == "market.trade.received"
    )

    assert event.schema_version == 1

    assert (
        event.source
        == "market-ingestor"
    )

    assert (
        event.occurred_at
        == TEST_TIMESTAMP
    )

    assert event.payload == {
        "trade_id": "trade-001",
        "symbol": "AAPL",
        "market": "US",
        "price": "229.51",
        "quantity": 100,
        "side": "BUY",
    }


def test_trade_event_is_json_serializable() -> None:
    trade = MarketTrade(
        trade_id="trade-001",
        symbol="AAPL",
        market=Market.US,
        price=Decimal("229.51"),
        quantity=100,
        side=TradeSide.BUY,
        timestamp=TEST_TIMESTAMP,
    )

    event = create_trade_event(
        trade
    )

    serialized = (
        event.to_event_json()
    )

    assert (
        '"event_type":"market.trade.received"'
        in serialized
    )

    assert (
        '"symbol":"AAPL"'
        in serialized
    )


# ============================================================
# Quote event factory
# ============================================================


def test_create_quote_event() -> None:
    quote = MarketQuote(
        symbol="AAPL",
        market=Market.US,
        bid_price=Decimal("229.50"),
        ask_price=Decimal("229.60"),
        bid_size=100,
        ask_size=120,
        timestamp=TEST_TIMESTAMP,
    )

    event = create_quote_event(
        quote
    )

    assert (
        event.event_type
        == "market.quote.received"
    )

    assert event.schema_version == 1

    assert (
        event.source
        == "market-ingestor"
    )

    assert (
        event.occurred_at
        == TEST_TIMESTAMP
    )

    assert event.payload == {
        "symbol": "AAPL",
        "market": "US",
        "bid_price": "229.50",
        "ask_price": "229.60",
        "bid_size": 100,
        "ask_size": 120,
        "mid_price": "229.55",
        "spread": "0.10",
    }


def test_quote_event_is_json_serializable() -> None:
    quote = MarketQuote(
        symbol="AAPL",
        market=Market.US,
        bid_price=Decimal("229.50"),
        ask_price=Decimal("229.60"),
        bid_size=100,
        ask_size=120,
        timestamp=TEST_TIMESTAMP,
    )

    event = create_quote_event(
        quote
    )

    serialized = (
        event.to_event_json()
    )

    assert (
        '"event_type":"market.quote.received"'
        in serialized
    )

    assert (
        '"symbol":"AAPL"'
        in serialized
    )


# ============================================================
# Trade mode
# ============================================================


def test_trade_mode_publishes_trade_event() -> None:
    runner, producer = build_runner(
        mode="trade",
    )

    runner.publish_once()

    assert (
        runner.published_count
        == 1
    )

    assert (
        len(producer.published)
        == 1
    )

    record = (
        producer.published[0]
    )

    assert (
        record.event.event_type
        == "market.trade.received"
    )

    assert (
        record.partition_key
        == "AAPL"
    )

    assert (
        record.event.payload[
            "symbol"
        ]
        == "AAPL"
    )


def test_trade_mode_only_publishes_trades() -> None:
    runner, producer = build_runner(
        mode="trade",
    )

    for _ in range(5):
        runner.publish_once()

    assert (
        runner.published_count
        == 5
    )

    assert (
        len(producer.published)
        == 5
    )

    assert all(
        record.event.event_type
        == "market.trade.received"
        for record
        in producer.published
    )


# ============================================================
# Quote mode
# ============================================================


def test_quote_mode_publishes_quote_event() -> None:
    runner, producer = build_runner(
        mode="quote",
    )

    runner.publish_once()

    assert (
        runner.published_count
        == 1
    )

    assert (
        len(producer.published)
        == 1
    )

    record = (
        producer.published[0]
    )

    assert (
        record.event.event_type
        == "market.quote.received"
    )

    assert (
        record.partition_key
        == "AAPL"
    )


def test_quote_mode_only_publishes_quotes() -> None:
    runner, producer = build_runner(
        mode="quote",
    )

    for _ in range(5):
        runner.publish_once()

    assert (
        runner.published_count
        == 5
    )

    assert all(
        record.event.event_type
        == "market.quote.received"
        for record
        in producer.published
    )


# ============================================================
# Both mode
# ============================================================


def test_both_mode_alternates_trade_and_quote() -> None:
    runner, producer = build_runner(
        mode="both",
    )

    for _ in range(6):
        runner.publish_once()

    event_types = [
        record.event.event_type
        for record
        in producer.published
    ]

    assert event_types == [
        "market.trade.received",
        "market.quote.received",
        "market.trade.received",
        "market.quote.received",
        "market.trade.received",
        "market.quote.received",
    ]


def test_both_mode_starts_with_trade() -> None:
    runner, producer = build_runner(
        mode="both",
    )

    runner.publish_once()

    assert (
        producer
        .published[0]
        .event
        .event_type
        == "market.trade.received"
    )


# ============================================================
# Partition key
# ============================================================


def test_runner_uses_symbol_as_partition_key() -> None:
    runner, producer = build_runner(
        mode="both",
    )

    for _ in range(10):
        runner.publish_once()

    assert all(
        record.partition_key
        == "AAPL"
        for record
        in producer.published
    )


# ============================================================
# published_count
# ============================================================


def test_published_count_starts_at_zero() -> None:
    runner, _ = build_runner()

    assert (
        runner.published_count
        == 0
    )


def test_published_count_increments_after_publish() -> None:
    runner, _ = build_runner()

    runner.publish_once()
    runner.publish_once()
    runner.publish_once()

    assert (
        runner.published_count
        == 3
    )


# ============================================================
# Run loop / max_events
# ============================================================


def test_run_stops_at_max_events() -> None:
    runner, producer = build_runner(
        mode="both",
        max_events=5,
        interval_seconds=0,
    )

    runner.run()

    assert (
        runner.published_count
        == 5
    )

    assert (
        len(producer.published)
        == 5
    )


def test_run_with_one_event() -> None:
    runner, producer = build_runner(
        mode="trade",
        max_events=1,
        interval_seconds=0,
    )

    runner.run()

    assert (
        runner.published_count
        == 1
    )

    assert (
        len(producer.published)
        == 1
    )


# ============================================================
# Graceful stop
# ============================================================


def test_stop_prevents_run_from_publishing() -> None:
    runner, producer = build_runner(
        mode="both",
        max_events=10,
        interval_seconds=0,
    )

    runner.stop()

    runner.run()

    assert (
        runner.published_count
        == 0
    )

    assert (
        producer.published
        == []
    )


# ============================================================
# Determinism
# ============================================================


def test_same_seed_produces_same_trade_payloads() -> None:
    runner_a, producer_a = build_runner(
        mode="trade",
        seed=12345,
    )

    runner_b, producer_b = build_runner(
        mode="trade",
        seed=12345,
    )

    for _ in range(10):
        runner_a.publish_once()
        runner_b.publish_once()

    payloads_a = [
        record.event.payload
        for record
        in producer_a.published
    ]

    payloads_b = [
        record.event.payload
        for record
        in producer_b.published
    ]

    assert payloads_a == payloads_b