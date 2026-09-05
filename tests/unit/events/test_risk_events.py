from __future__ import annotations

import json
from datetime import (
    UTC,
    datetime,
)
from decimal import Decimal
from uuid import uuid4

import pytest

from libs.domain.market import Market
from libs.domain.risk import (
    RiskAlert,
    RiskSeverity,
    RiskType,
)
from libs.events import (
    RISK_ALERT_DETECTED,
    RISK_ENGINE_SOURCE,
    RISK_EVENT_SCHEMA_VERSION,
    create_risk_alert_event,
)

pytestmark = pytest.mark.unit


TEST_TIMESTAMP = datetime(
    2026,
    9,
    5,
    6,
    0,
    0,
    tzinfo=UTC,
)


def build_alert() -> RiskAlert:
    return RiskAlert(
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
        message=(
            "Price move threshold exceeded"
        ),
        occurred_at=TEST_TIMESTAMP,
    )


def test_create_risk_alert_event() -> None:
    alert = build_alert()

    event = create_risk_alert_event(
        alert
    )

    assert (
        event.event_type
        == RISK_ALERT_DETECTED
    )

    assert (
        event.schema_version
        == RISK_EVENT_SCHEMA_VERSION
    )

    assert (
        event.source
        == RISK_ENGINE_SOURCE
    )

    assert (
        event.occurred_at
        == TEST_TIMESTAMP
    )


def test_risk_event_contains_alert_payload() -> None:
    event = create_risk_alert_event(
        build_alert()
    )

    payload = event.payload

    assert (
        payload["risk_type"]
        == "PRICE_MOVE_PERCENT"
    )

    assert (
        payload["severity"]
        == "CRITICAL"
    )

    assert (
        payload["market"]
        == "US"
    )

    assert (
        payload["symbol"]
        == "AAPL"
    )

    assert (
        Decimal(
            payload["observed_value"]
        )
        == Decimal("-6")
    )

    assert (
        Decimal(
            payload["threshold"]
        )
        == Decimal("5")
    )


def test_risk_event_preserves_correlation_id() -> None:
    correlation_id = uuid4()

    event = create_risk_alert_event(
        build_alert(),
        correlation_id=correlation_id,
    )

    assert (
        event.correlation_id
        == correlation_id
    )


def test_risk_event_preserves_causation_id() -> None:
    causation_id = uuid4()

    event = create_risk_alert_event(
        build_alert(),
        causation_id=causation_id,
    )

    assert (
        event.causation_id
        == causation_id
    )


def test_risk_event_generates_correlation_id_when_missing() -> None:
    event = create_risk_alert_event(
        build_alert()
    )

    assert event.correlation_id


def test_risk_event_is_json_serializable() -> None:
    event = create_risk_alert_event(
        build_alert()
    )

    text = event.to_event_json()

    payload = json.loads(
        text
    )

    assert (
        payload["event_type"]
        == "risk.alert.detected"
    )

    assert (
        payload["payload"]["symbol"]
        == "AAPL"
    )

    assert (
        payload["payload"]["severity"]
        == "CRITICAL"
    )


def test_risk_event_uses_alert_id_in_payload() -> None:
    alert = build_alert()

    event = create_risk_alert_event(
        alert
    )

    assert (
        event.payload["alert_id"]
        == str(alert.alert_id)
    )