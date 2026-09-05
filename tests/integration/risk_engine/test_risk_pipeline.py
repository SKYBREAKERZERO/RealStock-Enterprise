from __future__ import annotations

import json
import time
from datetime import (
    UTC,
    datetime,
    timedelta,
)
from decimal import Decimal
from uuid import uuid4

import pytest

from libs.aws import (
    get_eventbridge_client,
    get_sqs_client,
)
from libs.domain.market import (
    Market,
    MarketQuote,
)
from libs.events import (
    create_market_quote_event,
)
from services.risk_engine import (
    EVENTBRIDGE_RISK_SOURCE,
    EventBridgeRiskEventPublisher,
    InMemoryQuoteStateStore,
    RiskEngineService,
)

pytestmark = pytest.mark.integration


BASE_TIMESTAMP = datetime(
    2026,
    9,
    5,
    10,
    0,
    tzinfo=UTC,
)


def build_quote(
    *,
    price: Decimal,
    seconds: int,
) -> MarketQuote:
    return MarketQuote(
        symbol="AAPL",
        market=Market.US,
        bid_price=price,
        ask_price=price,
        bid_size=100,
        ask_size=100,
        timestamp=(
            BASE_TIMESTAMP
            + timedelta(
                seconds=seconds
            )
        ),
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
        "risk pipeline event was not "
        "delivered to SQS"
    )


def test_market_quotes_generate_risk_event_and_route_to_sqs() -> None:
    eventbridge = (
        get_eventbridge_client()
    )

    sqs = get_sqs_client()

    suffix = uuid4().hex[:8]

    queue_name = (
        f"realstock-risk-pipeline-"
        f"{suffix}"
    )

    rule_name = (
        f"realstock-risk-pipeline-rule-"
        f"{suffix}"
    )

    queue_url = ""

    try:
        # -------------------------------------------------
        # Infrastructure fixture
        # -------------------------------------------------

        queue_response = (
            sqs.create_queue(
                QueueName=queue_name
            )
        )

        queue_url = (
            queue_response["QueueUrl"]
        )

        attributes = (
            sqs.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=[
                    "QueueArn"
                ],
            )
        )

        queue_arn = (
            attributes[
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
                    "Effect":
                        "Allow",
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
                            "risk-pipeline-sqs",
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

        # -------------------------------------------------
        # Application pipeline
        # -------------------------------------------------

        state = (
            InMemoryQuoteStateStore()
        )

        risk_engine = (
            RiskEngineService(
                state_store=state,
            )
        )

        publisher = (
            EventBridgeRiskEventPublisher()
        )

        # Quote #1 establishes keyed state.
        first_quote = build_quote(
            price=Decimal("100"),
            seconds=1,
        )

        first_market_event = (
            create_market_quote_event(
                first_quote
            )
        )

        first_result = (
            risk_engine.process_event(
                first_market_event
            )
        )

        assert first_result is None

        stored_quote = (
            state.get_quote(
                market=Market.US,
                symbol="AAPL",
            )
        )

        assert stored_quote is not None

        assert (
            stored_quote.mid_price
            == Decimal("100")
        )

        # Quote #2 causes a -6% move.
        second_quote = build_quote(
            price=Decimal("94"),
            seconds=2,
        )

        second_market_event = (
            create_market_quote_event(
                second_quote
            )
        )

        risk_event = (
            risk_engine.process_event(
                second_market_event
            )
        )

        assert risk_event is not None

        assert (
            risk_event.event_type
            == "risk.alert.detected"
        )

        assert (
            risk_event.correlation_id
            == second_market_event.correlation_id
        )

        assert (
            risk_event.causation_id
            == second_market_event.event_id
        )

        assert (
            risk_event.payload["symbol"]
            == "AAPL"
        )

        assert (
            risk_event.payload["market"]
            == "US"
        )

        assert (
            risk_event.payload["severity"]
            == "CRITICAL"
        )

        assert (
            Decimal(
                risk_event.payload[
                    "observed_value"
                ]
            )
            == Decimal("-6")
        )

        # -------------------------------------------------
        # Publish risk event
        # -------------------------------------------------

        publish_result = (
            publisher.publish(
                risk_event
            )
        )

        assert publish_result.event_id

        # -------------------------------------------------
        # Verify EventBridge → SQS delivery
        # -------------------------------------------------

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
                second_market_event.correlation_id
            )
        )

        assert (
            detail["causation_id"]
            == str(
                second_market_event.event_id
            )
        )

        assert (
            detail["payload"]["symbol"]
            == "AAPL"
        )

        assert (
            detail["payload"]["market"]
            == "US"
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

        # Processing state must have advanced.
        latest_state = (
            state.get_quote(
                market=Market.US,
                symbol="AAPL",
            )
        )

        assert latest_state is not None

        assert (
            latest_state.mid_price
            == Decimal("94")
        )

    finally:
        try:
            eventbridge.remove_targets(
                Rule=rule_name,
                EventBusName="default",
                Ids=[
                    "risk-pipeline-sqs"
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