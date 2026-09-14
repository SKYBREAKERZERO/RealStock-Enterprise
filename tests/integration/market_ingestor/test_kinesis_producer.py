from __future__ import annotations

import json
import time
from typing import Any

import pytest
from botocore.exceptions import ClientError

from libs.aws import get_kinesis_client
from libs.events.envelope import EventEnvelope
from services.market_ingestor.producer import (
    KinesisMarketEventProducer,
    PublishResult,
)

pytestmark = pytest.mark.integration


# ============================================================
# Test configuration
# ============================================================

STREAM_NAME = "realstock-market-events-local"

STREAM_WAIT_RETRY_COUNT = 40
STREAM_WAIT_INTERVAL_SECONDS = 0.25

READ_RETRY_COUNT = 30
READ_RETRY_INTERVAL_SECONDS = 0.25


# ============================================================
# Kinesis bootstrap
# ============================================================


def ensure_stream_exists() -> None:
    """
    Ensure the LocalStack Kinesis stream exists and is ACTIVE.

    The integration test must be repeatable and must not depend
    on manually running init_kinesis.py before pytest.
    """

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

    for _ in range(STREAM_WAIT_RETRY_COUNT):
        try:
            response = client.describe_stream_summary(
                StreamName=STREAM_NAME,
            )

            status = response[
                "StreamDescriptionSummary"
            ]["StreamStatus"]

            if status == "ACTIVE":
                return

        except ClientError:
            pass

        time.sleep(
            STREAM_WAIT_INTERVAL_SECONDS
        )

    raise RuntimeError(
        "Kinesis stream did not become ACTIVE: "
        f"{STREAM_NAME}"
    )


# ============================================================
# Shard helpers
# ============================================================


def create_latest_iterators() -> dict[str, str]:
    """
    Create a LATEST iterator for every shard.

    The iterators are created before publishing the test event,
    so historical events already present in the stream are not
    considered part of this test.
    """

    client = get_kinesis_client()

    response = client.list_shards(
        StreamName=STREAM_NAME,
    )

    shards = response.get(
        "Shards",
        [],
    )

    if not shards:
        raise RuntimeError(
            "No shards found for Kinesis stream: "
            f"{STREAM_NAME}"
        )

    iterators: dict[str, str] = {}

    for shard in shards:
        shard_id = shard["ShardId"]

        iterator_response = (
            client.get_shard_iterator(
                StreamName=STREAM_NAME,
                ShardId=shard_id,
                ShardIteratorType="LATEST",
            )
        )

        shard_iterator = (
            iterator_response.get(
                "ShardIterator"
            )
        )

        if shard_iterator is None:
            raise RuntimeError(
                "Could not obtain shard iterator: "
                f"{shard_id}"
            )

        iterators[
            shard_id
        ] = shard_iterator

    return iterators


# ============================================================
# Event reader
# ============================================================


def wait_for_event(
    *,
    shard_iterator: str,
    event_id: str,
) -> dict[str, Any] | None:
    """
    Poll a Kinesis shard until the expected event is found.

    Kinesis delivery is asynchronous, so the test retries until
    the event appears or the retry budget is exhausted.
    """

    client = get_kinesis_client()

    current_iterator = (
        shard_iterator
    )

    for _ in range(READ_RETRY_COUNT):
        response = client.get_records(
            ShardIterator=current_iterator,
            Limit=100,
        )

        records = response.get(
            "Records",
            [],
        )

        for record in records:
            raw_data = record[
                "Data"
            ]

            if isinstance(
                raw_data,
                bytes,
            ):
                raw_payload = (
                    raw_data.decode(
                        "utf-8"
                    )
                )
            else:
                raw_payload = str(
                    raw_data
                )

            event = json.loads(
                raw_payload
            )

            if (
                event.get("event_id")
                == event_id
            ):
                return event

        next_iterator = response.get(
            "NextShardIterator"
        )

        if next_iterator:
            current_iterator = (
                next_iterator
            )

        time.sleep(
            READ_RETRY_INTERVAL_SECONDS
        )

    return None


# ============================================================
# Integration test
# ============================================================


def test_publish_market_event_to_kinesis() -> None:
    """
    Verify the complete event publishing path:

        EventEnvelope
            ↓
        KinesisMarketEventProducer
            ↓
        LocalStack Kinesis
            ↓
        Shard
            ↓
        GetRecords
            ↓
        Event verified
    """

    # --------------------------------------------------------
    # Arrange
    # --------------------------------------------------------

    ensure_stream_exists()

    shard_iterators = (
        create_latest_iterators()
    )

    event = EventEnvelope[
        dict[str, object]
    ](
        event_type="market.trade.received",
        schema_version=1,
        source="market-ingestor",
        payload={
            "trade_id": "pytest-trade-001",
            "symbol": "AAPL",
            "market": "US",
            "price": "229.51",
            "quantity": 100,
            "side": "BUY",
        },
    )

    producer = (
        KinesisMarketEventProducer(
            stream_name=STREAM_NAME,
        )
    )

    # --------------------------------------------------------
    # Act
    # --------------------------------------------------------

    result = producer.publish(
        event=event,
        partition_key="AAPL",
    )

    # --------------------------------------------------------
    # Producer contract validation
    # --------------------------------------------------------

    assert isinstance(
        result,
        PublishResult,
    )

    assert result.shard_id

    assert result.sequence_number

    shard_id = (
        result.shard_id
    )

    assert (
        shard_id
        in shard_iterators
    )

    # --------------------------------------------------------
    # Read event back from Kinesis
    # --------------------------------------------------------

    received_event = wait_for_event(
        shard_iterator=(
            shard_iterators[
                shard_id
            ]
        ),
        event_id=str(
            event.event_id
        ),
    )

    assert (
        received_event
        is not None
    )

    # --------------------------------------------------------
    # Envelope validation
    # --------------------------------------------------------

    assert (
        received_event[
            "event_id"
        ]
        == str(
            event.event_id
        )
    )

    assert (
        received_event[
            "event_type"
        ]
        == "market.trade.received"
    )

    assert (
        received_event[
            "schema_version"
        ]
        == 1
    )

    assert (
        received_event[
            "source"
        ]
        == "market-ingestor"
    )

    assert (
        received_event[
            "correlation_id"
        ]
        == str(
            event.correlation_id
        )
    )

    assert (
        received_event[
            "causation_id"
        ]
        is None
    )

    assert (
        received_event[
            "occurred_at"
        ]
    )

    # --------------------------------------------------------
    # Payload validation
    # --------------------------------------------------------

    payload = (
        received_event[
            "payload"
        ]
    )

    assert (
        payload[
            "trade_id"
        ]
        == "pytest-trade-001"
    )

    assert (
        payload[
            "symbol"
        ]
        == "AAPL"
    )

    assert (
        payload[
            "market"
        ]
        == "US"
    )

    assert (
        payload[
            "price"
        ]
        == "229.51"
    )

    assert (
        payload[
            "quantity"
        ]
        == 100
    )

    assert (
        payload[
            "side"
        ]
        == "BUY"
    )