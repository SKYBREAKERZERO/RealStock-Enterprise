from __future__ import annotations

import json
import time
from typing import Any

import pytest
from botocore.exceptions import ClientError

from libs.aws import get_kinesis_client
from services.market_ingestor.producer import (
    KinesisMarketEventProducer,
)
from services.market_ingestor.providers.mock import (
    MockMarketDataProvider,
)
from services.market_ingestor.runner import (
    MarketIngestorRunner,
    RunnerConfig,
)


pytestmark = pytest.mark.integration


# ============================================================
# Configuration
# ============================================================

STREAM_NAME = "realstock-market-events-local"

EVENT_COUNT = 6

STREAM_WAIT_RETRY_COUNT = 40
STREAM_WAIT_INTERVAL_SECONDS = 0.25

READ_RETRY_COUNT = 40
READ_RETRY_INTERVAL_SECONDS = 0.25


# ============================================================
# Kinesis bootstrap
# ============================================================


def ensure_stream_exists() -> None:
    """
    Ensure the LocalStack Kinesis stream exists and is ACTIVE.

    This test must be repeatable and must not require a manual
    init_kinesis.py execution before pytest.
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

    for _ in range(
        STREAM_WAIT_RETRY_COUNT
    ):
        try:
            response = (
                client.describe_stream_summary(
                    StreamName=STREAM_NAME,
                )
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
# Shard iterator
# ============================================================


def create_latest_iterators() -> dict[str, str]:
    """
    Create LATEST iterators before running the ingestion pipeline.

    This ensures that historical records already stored in the
    LocalStack stream are excluded from this test.
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
            "No shards found for stream: "
            f"{STREAM_NAME}"
        )

    iterators: dict[str, str] = {}

    for shard in shards:
        shard_id = shard[
            "ShardId"
        ]

        response = (
            client.get_shard_iterator(
                StreamName=STREAM_NAME,
                ShardId=shard_id,
                ShardIteratorType="LATEST",
            )
        )

        iterator = response.get(
            "ShardIterator"
        )

        if iterator is None:
            raise RuntimeError(
                "Could not create shard "
                f"iterator for {shard_id}"
            )

        iterators[
            shard_id
        ] = iterator

    return iterators


# ============================================================
# Record reader
# ============================================================


def decode_record(
    record: dict[str, Any],
) -> dict[str, Any]:
    """
    Decode a raw Kinesis record into a convenient test structure.
    """

    raw_data = record[
        "Data"
    ]

    if isinstance(
        raw_data,
        bytes,
    ):
        text = raw_data.decode(
            "utf-8"
        )

    else:
        text = str(
            raw_data
        )

    event = json.loads(
        text
    )

    return {
        "partition_key": record[
            "PartitionKey"
        ],
        "sequence_number": record[
            "SequenceNumber"
        ],
        "event": event,
    }


def wait_for_records(
    *,
    shard_iterators: dict[str, str],
    expected_count: int,
) -> list[dict[str, Any]]:
    """
    Poll every Kinesis shard until the expected number of records
    has been collected or the retry budget is exhausted.
    """

    client = get_kinesis_client()

    current_iterators = dict(
        shard_iterators
    )

    received: list[
        dict[str, Any]
    ] = []

    seen_sequence_numbers: set[
        str
    ] = set()

    for _ in range(
        READ_RETRY_COUNT
    ):
        for (
            shard_id,
            shard_iterator,
        ) in list(
            current_iterators.items()
        ):
            response = (
                client.get_records(
                    ShardIterator=(
                        shard_iterator
                    ),
                    Limit=100,
                )
            )

            records = response.get(
                "Records",
                [],
            )

            for record in records:
                sequence_number = record[
                    "SequenceNumber"
                ]

                # Defensive deduplication for a repeatable
                # integration test.
                if (
                    sequence_number
                    in seen_sequence_numbers
                ):
                    continue

                seen_sequence_numbers.add(
                    sequence_number
                )

                received.append(
                    decode_record(
                        record
                    )
                )

            next_iterator = (
                response.get(
                    "NextShardIterator"
                )
            )

            if next_iterator:
                current_iterators[
                    shard_id
                ] = next_iterator

        if (
            len(received)
            >= expected_count
        ):
            return received

        time.sleep(
            READ_RETRY_INTERVAL_SECONDS
        )

    return received


# ============================================================
# Integration test
# ============================================================


def test_complete_market_ingestion_pipeline() -> None:
    """
    Verify the complete RealStock market ingestion pipeline:

        Mock Provider
            ↓
        Market Domain
            ↓
        Event Envelope
            ↓
        Runner
            ↓
        Kinesis Producer
            ↓
        LocalStack Kinesis
            ↓
        Consumer-side record verification
    """

    # --------------------------------------------------------
    # Arrange
    # --------------------------------------------------------

    ensure_stream_exists()

    shard_iterators = (
        create_latest_iterators()
    )

    config = RunnerConfig(
        stream_name=STREAM_NAME,
        mode="both",
        interval_seconds=0,
        max_events=EVENT_COUNT,
        seed=42,
    )

    provider = (
        MockMarketDataProvider(
            seed=config.seed,
        )
    )

    producer = (
        KinesisMarketEventProducer(
            stream_name=(
                config.stream_name
            ),
        )
    )

    runner = MarketIngestorRunner(
        config=config,
        provider=provider,
        producer=producer,
    )

    # --------------------------------------------------------
    # Act
    # --------------------------------------------------------

    runner.run()

    records = wait_for_records(
        shard_iterators=(
            shard_iterators
        ),
        expected_count=(
            EVENT_COUNT
        ),
    )

    # --------------------------------------------------------
    # Runner validation
    # --------------------------------------------------------

    assert (
        runner.published_count
        == EVENT_COUNT
    )

    # --------------------------------------------------------
    # Kinesis validation
    # --------------------------------------------------------

    assert (
        len(records)
        == EVENT_COUNT
    )

    events = [
        record["event"]
        for record
        in records
    ]

    # --------------------------------------------------------
    # Event IDs must be unique
    # --------------------------------------------------------

    event_ids = {
        event["event_id"]
        for event
        in events
    }

    assert (
        len(event_ids)
        == EVENT_COUNT
    )

    # --------------------------------------------------------
    # Sequence numbers must be unique
    # --------------------------------------------------------

    sequence_numbers = {
        record[
            "sequence_number"
        ]
        for record
        in records
    }

    assert (
        len(sequence_numbers)
        == EVENT_COUNT
    )

    # --------------------------------------------------------
    # Both mode must alternate trade / quote
    # --------------------------------------------------------

    event_types = [
        event[
            "event_type"
        ]
        for event
        in events
    ]

    assert event_types == [
        "market.trade.received",
        "market.quote.received",
        "market.trade.received",
        "market.quote.received",
        "market.trade.received",
        "market.quote.received",
    ]

    # --------------------------------------------------------
    # Envelope validation
    # --------------------------------------------------------

    for event in events:
        assert (
            event[
                "schema_version"
            ]
            == 1
        )

        assert (
            event[
                "source"
            ]
            == "market-ingestor"
        )

        assert event[
            "event_id"
        ]

        assert event[
            "correlation_id"
        ]

        assert event[
            "occurred_at"
        ]

        assert (
            event[
                "causation_id"
            ]
            is None
        )

        assert isinstance(
            event[
                "payload"
            ],
            dict,
        )

    # --------------------------------------------------------
    # Partition-key contract
    # --------------------------------------------------------

    for record in records:
        event = record[
            "event"
        ]

        payload = event[
            "payload"
        ]

        assert (
            record[
                "partition_key"
            ]
            == payload[
                "symbol"
            ]
        )

    # --------------------------------------------------------
    # Trade event validation
    # --------------------------------------------------------

    trade_events = [
        event
        for event
        in events
        if event[
            "event_type"
        ]
        == "market.trade.received"
    ]

    assert (
        len(trade_events)
        == 3
    )

    for event in trade_events:
        payload = event[
            "payload"
        ]

        assert payload[
            "trade_id"
        ]

        assert payload[
            "symbol"
        ]

        assert payload[
            "market"
        ] in {
            "US",
            "JP",
        }

        assert (
            float(
                payload[
                    "price"
                ]
            )
            > 0
        )

        assert (
            payload[
                "quantity"
            ]
            > 0
        )

        assert payload[
            "side"
        ] in {
            "BUY",
            "SELL",
        }

    # --------------------------------------------------------
    # Quote event validation
    # --------------------------------------------------------

    quote_events = [
        event
        for event
        in events
        if event[
            "event_type"
        ]
        == "market.quote.received"
    ]

    assert (
        len(quote_events)
        == 3
    )

    for event in quote_events:
        payload = event[
            "payload"
        ]

        bid_price = float(
            payload[
                "bid_price"
            ]
        )

        ask_price = float(
            payload[
                "ask_price"
            ]
        )

        assert payload[
            "symbol"
        ]

        assert payload[
            "market"
        ] in {
            "US",
            "JP",
        }

        assert (
            bid_price
            > 0
        )

        assert (
            ask_price
            > 0
        )

        assert (
            bid_price
            <= ask_price
        )

        assert (
            payload[
                "bid_size"
            ]
            > 0
        )

        assert (
            payload[
                "ask_size"
            ]
            > 0
        )