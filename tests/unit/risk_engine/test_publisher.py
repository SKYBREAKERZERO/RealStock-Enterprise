from __future__ import annotations

from datetime import (
    UTC,
    datetime,
)
from decimal import Decimal
from unittest.mock import Mock

import pytest

from libs.domain.market import Market
from libs.domain.risk import (
    RiskAlert,
    RiskSeverity,
    RiskType,
)
from libs.events import (
    create_risk_alert_event,
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