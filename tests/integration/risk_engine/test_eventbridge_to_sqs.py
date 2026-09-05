from __future__ import annotations

import json
import time
from datetime import (
    UTC,
    datetime,
)
from decimal import Decimal
from uuid import uuid4

import pytest

from libs.aws import (
    get_eventbridge_client,
    get_sqs_client,
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
from services.risk_engine import (
    EVENTBRIDGE_RISK_SOURCE,
    EventBridgeRiskEventPublisher,
)

pytestmark = pytest.mark.integration


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
            9,
            30,
            tzinfo=UTC,
        ),
    )

    return create_risk_alert_event(
        alert
    )


def receive_message(
    *,
    sqs_client,
    queue_url: str,
) -> dict:
    for _ in range(20):
        response = (
            sqs_client.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=1,
            )
        )

        messages = response.get(
            "Messages",
            [],
        )

        if messages:
            return messages[0]

        time.sleep(0.25)

    raise AssertionError(
        "risk event was not delivered "
        "to SQS"
    )


def test_risk_event_routes_from_eventbridge_to_sqs() -> None:
    eventbridge = (
        get_eventbridge_client()
    )

    sqs = get_sqs_client()

    suffix = uuid4().hex[:8]

    queue_name = (
        f"realstock-risk-alerts-"
        f"{suffix}"
    )

    rule_name = (
        f"realstock-risk-alert-rule-"
        f"{suffix}"
    )

    queue_url = ""

    try:
        queue_response = (
            sqs.create_queue(
                QueueName=queue_name
            )
        )

        queue_url = (
            queue_response["QueueUrl"]
        )

        queue_attributes = (
            sqs.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=[
                    "QueueArn"
                ],
            )
        )

        queue_arn = (
            queue_attributes[
                "Attributes"
            ]["QueueArn"]
        )

        event_pattern = {
            "source": [
                EVENTBRIDGE_RISK_SOURCE
            ],
            "detail-type": [
                "risk.alert.detected"
            ],
        }

        rule_response = (
            eventbridge.put_rule(
                Name=rule_name,
                EventPattern=json.dumps(
                    event_pattern
                ),
                State="ENABLED",
                EventBusName="default",
            )
        )

        rule_arn = (
            rule_response["RuleArn"]
        )

        queue_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid":
                        "AllowEventBridgeSendMessage",
                    "Effect": "Allow",
                    "Principal": {
                        "Service":
                            "events.amazonaws.com"
                    },
                    "Action":
                        "sqs:SendMessage",
                    "Resource":
                        queue_arn,
                    "Condition": {
                        "ArnEquals": {
                            "aws:SourceArn":
                                rule_arn
                        }
                    },
                }
            ],
        }

        sqs.set_queue_attributes(
            QueueUrl=queue_url,
            Attributes={
                "Policy": json.dumps(
                    queue_policy
                )
            },
        )

        targets_response = (
            eventbridge.put_targets(
                Rule=rule_name,
                EventBusName="default",
                Targets=[
                    {
                        "Id":
                            "risk-alert-sqs",
                        "Arn":
                            queue_arn,
                    }
                ],
            )
        )

        assert (
            targets_response[
                "FailedEntryCount"
            ]
            == 0
        )

        publisher = (
            EventBridgeRiskEventPublisher()
        )

        risk_event = (
            build_risk_event()
        )

        publish_result = (
            publisher.publish(
                risk_event
            )
        )

        assert publish_result.event_id

        message = receive_message(
            sqs_client=sqs,
            queue_url=queue_url,
        )

        outer_event = json.loads(
            message["Body"]
        )

        assert (
            outer_event["source"]
            == EVENTBRIDGE_RISK_SOURCE
        )

        assert (
            outer_event["detail-type"]
            == "risk.alert.detected"
        )

        detail = outer_event[
            "detail"
        ]

        assert (
            detail["event_type"]
            == "risk.alert.detected"
        )

        assert (
            detail["event_id"]
            == str(
                risk_event.event_id
            )
        )

        assert (
            detail["correlation_id"]
            == str(
                risk_event.correlation_id
            )
        )

        assert (
            detail["payload"]["symbol"]
            == "AAPL"
        )

        assert (
            detail["payload"]["severity"]
            == "CRITICAL"
        )

        assert (
            Decimal(
                detail["payload"][
                    "observed_value"
                ]
            )
            == Decimal("-6")
        )

    finally:
        try:
            eventbridge.remove_targets(
                Rule=rule_name,
                EventBusName="default",
                Ids=[
                    "risk-alert-sqs"
                ],
                Force=True,
            )
        except Exception:
            pass

        try:
            eventbridge.delete_rule(
                Name=rule_name,
                EventBusName="default",
                Force=True,
            )
        except Exception:
            pass

        if queue_url:
            try:
                sqs.delete_queue(
                    QueueUrl=queue_url
                )
            except Exception:
                pass