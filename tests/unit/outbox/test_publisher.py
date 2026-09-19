from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import Mock
from uuid import UUID

import pytest

from libs.database.repositories.outbox import (
    ClaimedOutboxEvent,
)
from services.outbox_dispatcher.publisher import (
    EventBridgeOutboxPublisher,
)

pytestmark = pytest.mark.unit


def _claimed_event() -> ClaimedOutboxEvent:
    return ClaimedOutboxEvent(
        id=UUID(
            "11111111-1111-1111-1111-111111111111"
        ),
        event_id=UUID(
            "22222222-2222-2222-2222-222222222222"
        ),
        aggregate_type="portfolio",
        aggregate_id=(
            "33333333-3333-3333-3333-333333333333"
        ),
        event_type="portfolio.created",
        schema_version=1,
        source="portfolio-api",
        correlation_id=UUID(
            "44444444-4444-4444-4444-444444444444"
        ),
        causation_id=None,
        trace_context={
            "traceparent": (
                "00-"
                "0123456789abcdef0123456789abcdef-"
                "0123456789abcdef-01"
            ),
        },
        payload={
            "portfolio_id": (
                "33333333-3333-3333-3333-333333333333"
            ),
            "user_id": "user-001",
            "name": "Long Term Portfolio",
            "currency": "USD",
        },
        occurred_at=datetime(
            2026,
            9,
            19,
            3,
            0,
            tzinfo=UTC,
        ),
        attempt_count=0,
    )


def _successful_client() -> Mock:
    client = Mock()

    client.put_events.return_value = {
        "FailedEntryCount": 0,
        "Entries": [
            {
                "EventId": "aws-event-id-001",
            }
        ],
    }

    return client


def test_publish_sends_event_to_eventbridge() -> None:
    client = _successful_client()

    publisher = EventBridgeOutboxPublisher(
        client=client,
    )

    event = _claimed_event()

    result = publisher.publish(
        event
    )

    client.put_events.assert_called_once()

    call = client.put_events.call_args

    entries = call.kwargs[
        "Entries"
    ]

    assert len(entries) == 1

    entry = entries[0]

    assert (
        entry["Source"]
        == "realstock.portfolio-api"
    )

    assert (
        entry["DetailType"]
        == "portfolio.created"
    )

    assert (
        entry["EventBusName"]
        == "default"
    )

    assert (
        result.event_id
        == "aws-event-id-001"
    )


def test_publish_preserves_canonical_event_envelope() -> None:
    client = _successful_client()

    publisher = EventBridgeOutboxPublisher(
        client=client,
    )

    event = _claimed_event()

    publisher.publish(
        event
    )

    call = client.put_events.call_args

    detail = json.loads(
        call.kwargs[
            "Entries"
        ][0]["Detail"]
    )

    assert (
        detail["event_id"]
        == str(event.event_id)
    )

    assert (
        detail["event_type"]
        == event.event_type
    )

    assert (
        detail["schema_version"]
        == event.schema_version
    )

    assert (
        detail["source"]
        == event.source
    )

    assert (
        detail["correlation_id"]
        == str(event.correlation_id)
    )

    assert (
        detail["causation_id"]
        is None
    )

    assert (
        detail["trace_context"]
        == event.trace_context
    )

    assert (
        detail["payload"]
        == event.payload
    )


def test_publish_raises_when_eventbridge_reports_failure() -> None:
    client = Mock()

    client.put_events.return_value = {
        "FailedEntryCount": 1,
        "Entries": [
            {
                "ErrorCode": (
                    "InternalFailure"
                ),
                "ErrorMessage": (
                    "temporary failure"
                ),
            }
        ],
    }

    publisher = EventBridgeOutboxPublisher(
        client=client,
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "EventBridge failed to "
            "publish outbox event"
        ),
    ):
        publisher.publish(
            _claimed_event()
        )


def test_publish_raises_when_entry_contains_error_code() -> None:
    client = Mock()

    client.put_events.return_value = {
        "FailedEntryCount": 0,
        "Entries": [
            {
                "ErrorCode": (
                    "ThrottlingException"
                ),
                "ErrorMessage": (
                    "rate exceeded"
                ),
            }
        ],
    }

    publisher = EventBridgeOutboxPublisher(
        client=client,
    )

    with pytest.raises(
        RuntimeError,
        match="ThrottlingException",
    ):
        publisher.publish(
            _claimed_event()
        )


def test_publish_raises_when_event_id_is_missing() -> None:
    client = Mock()

    client.put_events.return_value = {
        "FailedEntryCount": 0,
        "Entries": [
            {},
        ],
    }

    publisher = EventBridgeOutboxPublisher(
        client=client,
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "did not contain EventId"
        ),
    ):
        publisher.publish(
            _claimed_event()
        )


@pytest.mark.parametrize(
    "event_bus_name",
    [
        "",
        " ",
        "   ",
    ],
)
def test_event_bus_name_must_not_be_empty(
    event_bus_name: str,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "event_bus_name must not be empty"
        ),
    ):
        EventBridgeOutboxPublisher(
            event_bus_name=event_bus_name,
            client=Mock(),
        )