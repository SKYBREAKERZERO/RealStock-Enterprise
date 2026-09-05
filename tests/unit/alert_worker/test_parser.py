from __future__ import annotations

import json
from datetime import (
    UTC,
    datetime,
)
from decimal import Decimal

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
from services.alert_worker import (
    EVENTBRIDGE_RISK_SOURCE,
    AlertMessageParser,
    InvalidAlertMessageError,
)

pytestmark = pytest.mark.unit


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
        message=(
            "Critical price move detected"
        ),
        occurred_at=datetime(
            2026,
            9,
            5,
            12,
            0,
            tzinfo=UTC,
        ),
    )

    return create_risk_alert_event(
        alert
    )


def build_sqs_message():
    risk_event = build_risk_event()

    outer_event = {
        "version": "0",
        "id": "eventbridge-001",
        "detail-type":
            "risk.alert.detected",
        "source":
            EVENTBRIDGE_RISK_SOURCE,
        "account":
            "000000000000",
        "time":
            "2026-09-05T12:00:00Z",
        "region":
            "ap-northeast-1",
        "resources": [],
        "detail":
            risk_event.to_event_dict(),
    }

    return {
        "MessageId": "sqs-001",
        "ReceiptHandle":
            "receipt-001",
        "Body": json.dumps(
            outer_event
        ),
    }, risk_event


def test_parse_valid_risk_message() -> None:
    parser = AlertMessageParser()

    message, risk_event = (
        build_sqs_message()
    )

    result = parser.parse(
        message
    )

    assert (
        result.source
        == EVENTBRIDGE_RISK_SOURCE
    )

    assert (
        result.detail_type
        == "risk.alert.detected"
    )

    assert (
        result.detail.event_id
        == risk_event.event_id
    )

    assert (
        result.detail.payload["symbol"]
        == "AAPL"
    )

    assert (
        result.detail.payload["severity"]
        == "CRITICAL"
    )


def test_rejects_missing_body() -> None:
    parser = AlertMessageParser()

    with pytest.raises(
        InvalidAlertMessageError,
        match="Body",
    ):
        parser.parse(
            {}
        )


def test_rejects_invalid_json() -> None:
    parser = AlertMessageParser()

    with pytest.raises(
        InvalidAlertMessageError,
        match="valid JSON",
    ):
        parser.parse(
            {
                "Body": "{broken"
            }
        )


def test_rejects_wrong_eventbridge_source() -> None:
    parser = AlertMessageParser()

    message, _ = (
        build_sqs_message()
    )

    body = json.loads(
        message["Body"]
    )

    body["source"] = (
        "realstock.other-service"
    )

    message["Body"] = (
        json.dumps(body)
    )

    with pytest.raises(
        InvalidAlertMessageError,
        match="source",
    ):
        parser.parse(
            message
        )


def test_rejects_wrong_detail_type() -> None:
    parser = AlertMessageParser()

    message, _ = (
        build_sqs_message()
    )

    body = json.loads(
        message["Body"]
    )

    body["detail-type"] = (
        "market.quote.received"
    )

    message["Body"] = (
        json.dumps(body)
    )

    with pytest.raises(
        InvalidAlertMessageError,
        match="detail-type",
    ):
        parser.parse(
            message
        )


def test_rejects_invalid_detail() -> None:
    parser = AlertMessageParser()

    message, _ = (
        build_sqs_message()
    )

    body = json.loads(
        message["Body"]
    )

    body["detail"] = {
        "broken": True
    }

    message["Body"] = (
        json.dumps(body)
    )

    with pytest.raises(
        InvalidAlertMessageError,
        match="EventEnvelope",
    ):
        parser.parse(
            message
        )


def test_rejects_mismatched_inner_event_type() -> None:
    parser = AlertMessageParser()

    message, _ = (
        build_sqs_message()
    )

    body = json.loads(
        message["Body"]
    )

    body["detail"]["event_type"] = (
        "market.quote.received"
    )

    message["Body"] = (
        json.dumps(body)
    )

    with pytest.raises(
        InvalidAlertMessageError,
        match="inner event_type",
    ):
        parser.parse(
            message
        )