from __future__ import annotations

import json
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
from services.alert_worker import (
    RiskNotificationFormatter,
    SnsRiskNotificationPublisher,
)

pytestmark = pytest.mark.unit


TOPIC_ARN = (
    "arn:aws:sns:"
    "ap-northeast-1:"
    "000000000000:"
    "realstock-risk-alerts"
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
        message=(
            "Critical price move detected"
        ),
        occurred_at=datetime(
            2026,
            9,
            5,
            13,
            0,
            tzinfo=UTC,
        ),
    )

    return create_risk_alert_event(
        alert
    )


def test_formatter_builds_subject() -> None:
    formatter = (
        RiskNotificationFormatter()
    )

    subject = (
        formatter.format_subject(
            event=build_risk_event()
        )
    )

    assert subject == (
        "[RealStock] CRITICAL "
        "US:AAPL"
    )


def test_formatter_builds_structured_message() -> None:
    formatter = (
        RiskNotificationFormatter()
    )

    event = build_risk_event()

    text = (
        formatter.format_message(
            event=event
        )
    )

    payload = json.loads(
        text
    )

    assert (
        payload["notification_type"]
        == "risk_alert"
    )

    assert (
        payload["event_id"]
        == str(event.event_id)
    )

    assert (
        payload["correlation_id"]
        == str(event.correlation_id)
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


def test_publish_risk_notification() -> None:
    client = Mock()

    client.publish.return_value = {
        "MessageId": "sns-message-001"
    }

    publisher = (
        SnsRiskNotificationPublisher(
            topic_arn=TOPIC_ARN,
            client=client,
        )
    )

    event = build_risk_event()

    result = publisher.publish(
        event
    )

    assert (
        result.message_id
        == "sns-message-001"
    )

    client.publish.assert_called_once()

    request = (
        client.publish.call_args.kwargs
    )

    assert (
        request["TopicArn"]
        == TOPIC_ARN
    )

    assert (
        request["Subject"]
        == "[RealStock] CRITICAL US:AAPL"
    )

    body = json.loads(
        request["Message"]
    )

    assert (
        body["event_id"]
        == str(event.event_id)
    )

    assert (
        body["severity"]
        == "CRITICAL"
    )

    attributes = (
        request["MessageAttributes"]
    )

    assert (
        attributes["severity"][
            "StringValue"
        ]
        == "CRITICAL"
    )

    assert (
        attributes["symbol"][
            "StringValue"
        ]
        == "AAPL"
    )


def test_rejects_non_risk_event() -> None:
    client = Mock()

    publisher = (
        SnsRiskNotificationPublisher(
            topic_arn=TOPIC_ARN,
            client=client,
        )
    )

    event = (
        build_risk_event()
        .model_copy(
            update={
                "event_type":
                    "market.quote.received"
            }
        )
    )

    with pytest.raises(
        ValueError,
        match="risk.alert.detected",
    ):
        publisher.publish(
            event
        )

    client.publish.assert_not_called()


def test_rejects_empty_topic_arn() -> None:
    with pytest.raises(
        ValueError,
        match="topic_arn",
    ):
        SnsRiskNotificationPublisher(
            topic_arn="   "
        )


def test_missing_message_id_raises_error() -> None:
    client = Mock()

    client.publish.return_value = {}

    publisher = (
        SnsRiskNotificationPublisher(
            topic_arn=TOPIC_ARN,
            client=client,
        )
    )

    with pytest.raises(
        RuntimeError,
        match="MessageId",
    ):
        publisher.publish(
            build_risk_event()
        )


def test_sns_failure_propagates() -> None:
    client = Mock()

    client.publish.side_effect = (
        RuntimeError(
            "SNS unavailable"
        )
    )

    publisher = (
        SnsRiskNotificationPublisher(
            topic_arn=TOPIC_ARN,
            client=client,
        )
    )

    with pytest.raises(
        RuntimeError,
        match="SNS unavailable",
    ):
        publisher.publish(
            build_risk_event()
        )