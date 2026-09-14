from __future__ import annotations

from datetime import (
    UTC,
    datetime,
)
from decimal import Decimal
from unittest.mock import Mock

import pytest

from libs.cache import MarketQuoteCache
from libs.domain.market import (
    Market,
    MarketQuote,
    MarketTrade,
    TradeSide,
)
from services.market_ingestor.producer import (
    KinesisMarketEventProducer,
    PublishResult,
)
from services.market_ingestor.service import (
    MarketIngestorService,
)

pytestmark = pytest.mark.unit


def build_quote() -> MarketQuote:
    return MarketQuote(
        symbol="AAPL",
        market=Market.US,
        bid_price=Decimal("210"),
        ask_price=Decimal("212"),
        bid_size=100,
        ask_size=120,
        timestamp=datetime(
            2026,
            9,
            5,
            4,
            0,
            0,
            tzinfo=UTC,
        ),
    )


def build_trade() -> MarketTrade:
    return MarketTrade(
        trade_id="trade-001",
        symbol="AAPL",
        market=Market.US,
        price=Decimal("211"),
        quantity=100,
        side=TradeSide.BUY,
        timestamp=datetime(
            2026,
            9,
            5,
            4,
            0,
            0,
            tzinfo=UTC,
        ),
    )


def build_publish_result() -> PublishResult:
    return PublishResult(
        shard_id="shardId-000000000000",
        sequence_number="123",
    )


def test_ingest_quote_publishes_then_caches_quote() -> None:
    producer = Mock(
        spec=KinesisMarketEventProducer
    )

    quote_cache = Mock(
        spec=MarketQuoteCache
    )

    result = build_publish_result()

    producer.publish.return_value = result

    service = MarketIngestorService(
        producer=producer,
        quote_cache=quote_cache,
    )

    quote = build_quote()

    actual = service.ingest_quote(
        quote
    )

    assert actual == result

    producer.publish.assert_called_once()

    call = producer.publish.call_args

    assert (
        call.kwargs["partition_key"]
        == "US:AAPL"
    )

    quote_cache.set_quote.assert_called_once_with(
        quote
    )


def test_ingest_quote_does_not_cache_when_publish_fails() -> None:
    producer = Mock(
        spec=KinesisMarketEventProducer
    )

    quote_cache = Mock(
        spec=MarketQuoteCache
    )

    producer.publish.side_effect = RuntimeError(
        "kinesis publish failed"
    )

    service = MarketIngestorService(
        producer=producer,
        quote_cache=quote_cache,
    )

    with pytest.raises(
        RuntimeError,
        match="kinesis publish failed",
    ):
        service.ingest_quote(
            build_quote()
        )

    quote_cache.set_quote.assert_not_called()


def test_cache_failure_does_not_fail_successful_ingestion() -> None:
    producer = Mock(
        spec=KinesisMarketEventProducer
    )

    quote_cache = Mock(
        spec=MarketQuoteCache
    )

    expected = build_publish_result()

    producer.publish.return_value = expected

    quote_cache.set_quote.side_effect = (
        RuntimeError(
            "redis unavailable"
        )
    )

    service = MarketIngestorService(
        producer=producer,
        quote_cache=quote_cache,
    )

    result = service.ingest_quote(
        build_quote()
    )

    assert result == expected

    producer.publish.assert_called_once()
    quote_cache.set_quote.assert_called_once()


def test_ingest_trade_does_not_update_quote_cache() -> None:
    producer = Mock(
        spec=KinesisMarketEventProducer
    )

    quote_cache = Mock(
        spec=MarketQuoteCache
    )

    expected = build_publish_result()

    producer.publish.return_value = expected

    service = MarketIngestorService(
        producer=producer,
        quote_cache=quote_cache,
    )

    result = service.ingest_trade(
        build_trade()
    )

    assert result == expected

    producer.publish.assert_called_once()

    call = producer.publish.call_args

    assert (
        call.kwargs["partition_key"]
        == "US:AAPL"
    )

    quote_cache.set_quote.assert_not_called()