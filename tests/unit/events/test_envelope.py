from __future__ import annotations

import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from libs.events.envelope import EventEnvelope

pytestmark = pytest.mark.unit


# =========================================================
# Core event contract
# =========================================================


def test_event_envelope_can_be_created() -> None:
    event = EventEnvelope(
        event_type="market.trade.received",
        source="market-ingestor",
        payload={
            "symbol": "AAPL",
        },
    )

    assert isinstance(
        event.event_id,
        UUID,
    )

    assert isinstance(
        event.correlation_id,
        UUID,
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

    assert event.payload == {
        "symbol": "AAPL",
    }


def test_event_id_is_unique() -> None:
    first = EventEnvelope(
        event_type="market.trade.received",
        source="market-ingestor",
        payload={},
    )

    second = EventEnvelope(
        event_type="market.trade.received",
        source="market-ingestor",
        payload={},
    )

    assert (
        first.event_id
        != second.event_id
    )


def test_correlation_id_is_unique_by_default() -> None:
    first = EventEnvelope(
        event_type="market.trade.received",
        source="market-ingestor",
        payload={},
    )

    second = EventEnvelope(
        event_type="market.trade.received",
        source="market-ingestor",
        payload={},
    )

    assert (
        first.correlation_id
        != second.correlation_id
    )


def test_explicit_correlation_id_is_preserved() -> None:
    correlation_id = uuid4()

    event = EventEnvelope(
        event_type="market.trade.received",
        source="market-ingestor",
        correlation_id=correlation_id,
        payload={},
    )

    assert (
        event.correlation_id
        == correlation_id
    )


def test_causation_id_can_be_provided() -> None:
    causation_id = uuid4()

    event = EventEnvelope(
        event_type="market.trade.received",
        source="market-ingestor",
        causation_id=causation_id,
        payload={},
    )

    assert (
        event.causation_id
        == causation_id
    )


# =========================================================
# Timestamp contract
# =========================================================


def test_occurred_at_is_timezone_aware() -> None:
    event = EventEnvelope(
        event_type="market.trade.received",
        source="market-ingestor",
        payload={},
    )

    assert (
        event.occurred_at.tzinfo
        is not None
    )

    assert (
        event.occurred_at.utcoffset()
        == UTC.utcoffset(
            event.occurred_at
        )
    )


def test_explicit_utc_timestamp_is_preserved() -> None:
    timestamp = datetime(
        2026,
        9,
        3,
        12,
        0,
        0,
        tzinfo=UTC,
    )

    event = EventEnvelope(
        event_type="market.trade.received",
        source="market-ingestor",
        occurred_at=timestamp,
        payload={},
    )

    assert (
        event.occurred_at
        == timestamp
    )


# =========================================================
# Serialization contract
# =========================================================


def test_event_json_is_valid_json() -> None:
    event = EventEnvelope(
        event_type="market.trade.received",
        source="market-ingestor",
        payload={
            "symbol": "AAPL",
        },
    )

    raw = event.to_event_json()

    document = json.loads(
        raw
    )

    assert (
        document["event_id"]
        == str(
            event.event_id
        )
    )

    assert (
        document["event_type"]
        == "market.trade.received"
    )

    assert (
        document["schema_version"]
        == 1
    )

    assert (
        document["source"]
        == "market-ingestor"
    )

    assert document["payload"] == {
        "symbol": "AAPL",
    }


def test_event_json_serializes_datetime_as_utc() -> None:
    timestamp = datetime(
        2026,
        9,
        3,
        12,
        0,
        0,
        tzinfo=UTC,
    )

    event = EventEnvelope(
        event_type="market.trade.received",
        source="market-ingestor",
        occurred_at=timestamp,
        payload={},
    )

    document = json.loads(
        event.to_event_json()
    )

    assert (
        document["occurred_at"]
        == "2026-09-03T12:00:00Z"
    )


def test_event_json_serializes_uuid_as_string() -> None:
    event_id = uuid4()
    correlation_id = uuid4()
    causation_id = uuid4()

    event = EventEnvelope(
        event_id=event_id,
        event_type="market.trade.received",
        source="market-ingestor",
        correlation_id=correlation_id,
        causation_id=causation_id,
        payload={},
    )

    document = json.loads(
        event.to_event_json()
    )

    assert (
        document["event_id"]
        == str(
            event_id
        )
    )

    assert (
        document["correlation_id"]
        == str(
            correlation_id
        )
    )

    assert (
        document["causation_id"]
        == str(
            causation_id
        )
    )


def test_payload_can_contain_nested_data() -> None:
    event = EventEnvelope(
        event_type="market.trade.received",
        source="market-ingestor",
        payload={
            "symbol": "AAPL",
            "trade": {
                "price": "229.51",
                "quantity": 100,
            },
        },
    )

    document = json.loads(
        event.to_event_json()
    )

    assert (
        document[
            "payload"
        ][
            "trade"
        ][
            "price"
        ]
        == "229.51"
    )

    assert (
        document[
            "payload"
        ][
            "trade"
        ][
            "quantity"
        ]
        == 100
    )


# =========================================================
# Validation contract
# =========================================================


def test_event_rejects_empty_event_type() -> None:
    with pytest.raises(
        (
            ValidationError,
            ValueError,
        )
    ):
        EventEnvelope(
            event_type="",
            source="market-ingestor",
            payload={},
        )


def test_event_rejects_empty_source() -> None:
    with pytest.raises(
        (
            ValidationError,
            ValueError,
        )
    ):
        EventEnvelope(
            event_type=(
                "market.trade.received"
            ),
            source="",
            payload={},
        )


# =========================================================
# Distributed trace transport contract
# =========================================================


def test_trace_context_can_be_serialized() -> None:
    traceparent = (
        "00-"
        "4bf92f3577b34da6a3ce929d0e0e4736-"
        "00f067aa0ba902b7-"
        "01"
    )

    event = EventEnvelope(
        event_type="risk.alert.detected",
        source="risk-engine",
        trace_context={
            "traceparent":
                traceparent,
        },
        payload={},
    )

    document = json.loads(
        event.to_event_json()
    )

    assert (
        document["trace_context"]
        == {
            "traceparent":
                traceparent,
        }
    )


def test_trace_context_round_trips_through_event_envelope() -> None:
    trace_context = {
        "traceparent": (
            "00-"
            "4bf92f3577b34da6a3ce929d0e0e4736-"
            "00f067aa0ba902b7-"
            "01"
        ),
        "tracestate": (
            "vendor=value"
        ),
    }

    original = EventEnvelope(
        event_type="risk.alert.detected",
        source="risk-engine",
        trace_context=trace_context,
        payload={
            "symbol": "AAPL",
        },
    )

    restored = (
        EventEnvelope
        .model_validate_json(
            original.to_event_json()
        )
    )

    assert (
        restored.trace_context
        == trace_context
    )

    assert (
        restored.event_id
        == original.event_id
    )

    assert (
        restored.correlation_id
        == original.correlation_id
    )


def test_missing_trace_context_preserves_existing_wire_contract() -> None:
    event = EventEnvelope(
        event_type="market.trade.received",
        source="market-ingestor",
        payload={},
    )

    document = json.loads(
        event.to_event_json()
    )

    assert (
        "trace_context"
        not in document
    )

    assert (
        "causation_id"
        in document
    )

    assert (
        document[
            "causation_id"
        ]
        is None
    )