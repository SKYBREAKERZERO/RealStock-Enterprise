from __future__ import annotations

import json
from datetime import (
    UTC,
    datetime,
)
from decimal import Decimal
from unittest.mock import Mock

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from libs.domain.market import Market
from libs.domain.risk import (
    RiskAlert,
    RiskSeverity,
    RiskType,
)
from libs.events import (
    create_risk_alert_event,
)
from libs.observability import (
    create_tracing_runtime,
)
from services.risk_engine import (
    EVENTBRIDGE_RISK_SOURCE,
    EventBridgeRiskEventPublisher,
)

pytestmark = pytest.mark.unit


TEST_TIMESTAMP = datetime(
    2026,
    9,
    5,
    9,
    0,
    tzinfo=UTC,
)


def build_risk_event():
    alert = RiskAlert(
        risk_type=(
            RiskType.PRICE_MOVE_PERCENT
        ),
        severity=(
            RiskSeverity.CRITICAL
        ),
        market=Market.US,
        symbol="AAPL",
        observed_value=Decimal("-6"),
        threshold=Decimal("5"),
        message="Critical price move",
        occurred_at=TEST_TIMESTAMP,
    )

    return create_risk_alert_event(
        alert
    )


def test_publish_risk_event() -> None:
    client = Mock()

    client.put_events.return_value = {
        "FailedEntryCount": 0,
        "Entries": [
            {
                "EventId": "event-001",
            }
        ],
    }

    publisher = (
        EventBridgeRiskEventPublisher(
            client=client
        )
    )

    event = build_risk_event()

    result = publisher.publish(
        event
    )

    assert (
        result.event_id
        == "event-001"
    )

    client.put_events.assert_called_once()

    entry = (
        client.put_events
        .call_args
        .kwargs["Entries"][0]
    )

    assert (
        entry["Source"]
        == EVENTBRIDGE_RISK_SOURCE
    )

    assert (
        entry["DetailType"]
        == "risk.alert.detected"
    )

    assert (
        entry["EventBusName"]
        == "default"
    )

    assert (
        entry["Detail"]
        == event.to_event_json()
    )


def test_rejects_non_risk_event() -> None:
    client = Mock()

    publisher = (
        EventBridgeRiskEventPublisher(
            client=client
        )
    )

    event = build_risk_event().model_copy(
        update={
            "event_type":
                "market.quote.received"
        }
    )

    with pytest.raises(
        ValueError,
        match=(
            "risk.alert.detected"
        ),
    ):
        publisher.publish(
            event
        )

    client.put_events.assert_not_called()


def test_publish_failure_raises_error() -> None:
    client = Mock()

    client.put_events.return_value = {
        "FailedEntryCount": 1,
        "Entries": [
            {
                "ErrorCode":
                    "InternalFailure",
                "ErrorMessage":
                    "temporary failure",
            }
        ],
    }

    publisher = (
        EventBridgeRiskEventPublisher(
            client=client
        )
    )

    with pytest.raises(
        RuntimeError,
    ):
        publisher.publish(
            build_risk_event()
        )


def test_missing_event_id_raises_error() -> None:
    client = Mock()

    client.put_events.return_value = {
        "FailedEntryCount": 0,
        "Entries": [
            {}
        ],
    }

    publisher = (
        EventBridgeRiskEventPublisher(
            client=client
        )
    )

    with pytest.raises(
        RuntimeError,
        match="EventId",
    ):
        publisher.publish(
            build_risk_event()
        )


def test_rejects_empty_event_bus_name() -> None:
    with pytest.raises(
        ValueError,
        match="event_bus_name",
    ):
        EventBridgeRiskEventPublisher(
            event_bus_name="   "
        )

def test_publish_injects_active_trace_context() -> None:
    client = Mock()

    client.put_events.return_value = {
        "FailedEntryCount": 0,
        "Entries": [
            {
                "EventId":
                    "eventbridge-001",
            }
        ],
    }

    exporter = InMemorySpanExporter()

    runtime = create_tracing_runtime(
        service_name="risk-engine",
        environment="test",
        exporter=exporter,
    )

    publisher = (
        EventBridgeRiskEventPublisher(
            client=client
        )
    )

    event = build_risk_event()

    try:
        with (
            runtime.tracer
            .start_as_current_span(
                "risk.process"
            )
        ):
            publisher.publish(
                event
            )

        entry = (
            client.put_events
            .call_args
            .kwargs["Entries"][0]
        )

        detail = json.loads(
            entry["Detail"]
        )

        trace_context = detail[
            "trace_context"
        ]

        assert (
            "traceparent"
            in trace_context
        )

        traceparent = (
            trace_context[
                "traceparent"
            ]
        )

        assert traceparent.startswith(
            "00-"
        )

        assert (
            len(
                traceparent.split(
                    "-"
                )[1]
            )
            == 32
        )

        assert (
            len(
                traceparent.split(
                    "-"
                )[2]
            )
            == 16
        )

        # The canonical input event is immutable and is not
        # mutated with transport trace metadata.
        assert (
            event.trace_context
            is None
        )

    finally:
        runtime.shutdown()


def test_publish_without_active_span_preserves_event_contract() -> None:
    client = Mock()

    client.put_events.return_value = {
        "FailedEntryCount": 0,
        "Entries": [
            {
                "EventId":
                    "eventbridge-001",
            }
        ],
    }

    publisher = (
        EventBridgeRiskEventPublisher(
            client=client
        )
    )

    event = build_risk_event()

    publisher.publish(
        event
    )

    entry = (
        client.put_events
        .call_args
        .kwargs["Entries"][0]
    )

    detail = json.loads(
        entry["Detail"]
    )

    assert (
        "trace_context"
        not in detail
    )