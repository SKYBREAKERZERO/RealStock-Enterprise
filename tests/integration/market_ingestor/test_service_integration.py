from __future__ import annotations

import json
import time
from datetime import (
    datetime,
    timezone,
)
from decimal import Decimal

import pytest
from botocore.exceptions import ClientError

from libs.aws import get_kinesis_client
from libs.cache import (
    MarketQuoteCache,
    get_redis_client,
)
from libs.domain.market import (
    Market,
    MarketQuote,
)
from services.market_ingestor.producer import (
    KinesisMarketEventProducer,
)
from services.market_ingestor.service import (
    MarketIngestorService,
)


pytestmark = pytest.mark.integration


STREAM_NAME = "realstock-market-events-local"

TEST_SYMBOL = "AAPL"

STREAM_WAIT_RETRIES = 40
STREAM_WAIT_SECONDS = 0.25

RECORD_WAIT_RETRIES = 40
RECORD_WAIT_SECONDS = 0.25


def ensure_stream_exists() -> None:
    client = get_kinesis_client()

    try:
        response = client.describe_stream_summary(
            StreamName=STREAM_NAME,
        )

        status = response[
            "StreamDescriptionSummary"
        ]["StreamStatus"]

        if status == "ACTIVE":
            return

    except ClientError as exc:
        error_code = (
            exc.response
            .get("Error", {})
            .get("Code")
        )

        if error_code != "ResourceNotFoundException":
            raise

        client.create_stream(
            StreamName=STREAM_NAME,
            ShardCount=1,
        )

    for _ in range(STREAM_WAIT_RETRIES):
        response = client.describe_stream_summary(
            StreamName=STREAM_NAME,
        )

        status = response[
            "StreamDescriptionSummary"
        ]["StreamStatus"]

        if status == "ACTIVE":
            return

        time.sleep(
            STREAM_WAIT_SECONDS
        )

    raise RuntimeError(
        "Kinesis stream did not become ACTIVE"
    )


def create_latest_iterator() -> str:
    client = get_kinesis_client()

    shards = client.list_shards(
        StreamName=STREAM_NAME,
    )["Shards"]

    if not shards:
        raise RuntimeError(
            "Kinesis stream has no shards"
        )

    shard_id = shards[0]["ShardId"]

    response = client.get_shard_iterator(
        StreamName=STREAM_NAME,
        ShardId=shard_id,
        ShardIteratorType="LATEST",
    )

    iterator = response.get(
        "ShardIterator"
    )

    if iterator is None:
        raise RuntimeError(
            "could not create shard iterator"
        )

    return iterator


def wait_for_record(
    shard_iterator: str,
) -> dict:
    client = get_kinesis_client()

    iterator = shard_iterator

    for _ in range(RECORD_WAIT_RETRIES):
        response = client.get_records(
            ShardIterator=iterator,
            Limit=10,
        )

        records = response.get(
            "Records",
            [],
        )

        if records:
            return records[0]

        next_iterator = response.get(
            "NextShardIterator"
        )

        if next_iterator is not None:
            iterator = next_iterator

        time.sleep(
            RECORD_WAIT_SECONDS
        )

    raise AssertionError(
        "Kinesis record was not received"
    )


def build_quote() -> MarketQuote:
    return MarketQuote(
        symbol=TEST_SYMBOL,
        market=Market.US,
        bid_price=Decimal("210.00"),
        ask_price=Decimal("212.00"),
        bid_size=100,
        ask_size=120,
        timestamp=datetime(
            2026,
            9,
            5,
            4,
            30,
            0,
            tzinfo=timezone.utc,
        ),
    )


@pytest.fixture(autouse=True)
def cleanup_quote():
    redis_client = get_redis_client()

    key = (
        "realstock:quote:"
        f"{Market.US.value}:"
        f"{TEST_SYMBOL}"
    )

    redis_client.delete(key)

    yield

    redis_client.delete(key)


def test_ingest_quote_writes_kinesis_and_redis() -> None:
    # Arrange
    ensure_stream_exists()

    shard_iterator = (
        create_latest_iterator()
    )

    producer = KinesisMarketEventProducer(
        stream_name=STREAM_NAME,
    )

    quote_cache = MarketQuoteCache(
        ttl_seconds=30,
    )

    service = MarketIngestorService(
        producer=producer,
        quote_cache=quote_cache,
    )

    quote = build_quote()

    # Act
    publish_result = service.ingest_quote(
        quote
    )

    # --------------------------------------------------------
    # Kinesis publish result
    # --------------------------------------------------------

    assert publish_result.shard_id
    assert publish_result.sequence_number

    # --------------------------------------------------------
    # Redis verification
    # --------------------------------------------------------

    cached_quote = quote_cache.get_quote(
        market=Market.US,
        symbol=TEST_SYMBOL,
    )

    assert cached_quote == quote

    assert (
        cached_quote.mid_price
        == Decimal("211.00")
    )

    redis_client = get_redis_client()

    key = (
        "realstock:quote:"
        f"{Market.US.value}:"
        f"{TEST_SYMBOL}"
    )

    ttl = redis_client.ttl(key)

    assert 0 < ttl <= 30

    # --------------------------------------------------------
    # Kinesis record verification
    # --------------------------------------------------------

    record = wait_for_record(
        shard_iterator
    )

    assert (
        record["PartitionKey"]
        == "US:AAPL"
    )

    payload = json.loads(
        record["Data"].decode("utf-8")
    )

    assert (
        payload["event_type"]
        == "market.quote.received"
    )

    assert (
        payload["source"]
        == "market-ingestor"
    )

    assert (
        payload["payload"]["symbol"]
        == "AAPL"
    )

    assert (
        payload["payload"]["market"]
        == "US"
    )

    assert (
        Decimal(
            payload["payload"]["bid_price"]
        )
        == Decimal("210.00")
    )

    assert (
        Decimal(
            payload["payload"]["ask_price"]
        )
        == Decimal("212.00")
    )