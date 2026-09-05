from __future__ import annotations

import json
from datetime import (
    UTC,
    datetime,
)
from decimal import Decimal
from uuid import uuid4

import pytest

from libs.aws import (
    get_dynamodb_client,
    get_sns_client,
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
from services.alert_worker import (
    DEFAULT_IDEMPOTENCY_TABLE_NAME,
    EVENTBRIDGE_RISK_SOURCE,
    AlertMessageParser,
    AlertProcessingStatus,
    AlertWorkerService,
    DynamoDbIdempotencyStore,
    IdempotencyStatus,
    SnsRiskNotificationPublisher,
    SqsAlertConsumer,
)

pytestmark = pytest.mark.integration


TABLE_NAME = (
    DEFAULT_IDEMPOTENCY_TABLE_NAME
)


def ensure_idempotency_table() -> None:
    client = get_dynamodb_client()

    try:
        client.describe_table(
            TableName=TABLE_NAME
        )
        return

    except (
        client.exceptions
        .ResourceNotFoundException
    ):
        pass

    client.create_table(
        TableName=TABLE_NAME,
        KeySchema=[
            {
                "AttributeName": "event_id",
                "KeyType": "HASH",
            }
        ],
        AttributeDefinitions=[
            {
                "AttributeName": "event_id",
                "AttributeType": "S",
            }
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    client.get_waiter(
        "table_exists"
    ).wait(
        TableName=TABLE_NAME
    )

    client.update_time_to_live(
        TableName=TABLE_NAME,
        TimeToLiveSpecification={
            "Enabled": True,
            "AttributeName": "expires_at",
        },
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
            15,
            0,
            tzinfo=UTC,
        ),
    )

    return create_risk_alert_event(
        alert
    )


def build_eventbridge_body(
    risk_event,
) -> str:
    outer_event = {
        "version": "0",
        "id": str(uuid4()),
        "detail-type":
            "risk.alert.detected",
        "source":
            EVENTBRIDGE_RISK_SOURCE,
        "account":
            "000000000000",
        "time":
            "2026-09-05T15:00:00Z",
        "region":
            "ap-northeast-1",
        "resources": [],
        "detail":
            risk_event.to_event_dict(),
    }

    return json.dumps(
        outer_event
    )


def receive_notification(
    *,
    client,
    queue_url: str,
) -> dict:
    for _ in range(10):
        response = (
            client.receive_message(
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

    raise AssertionError(
        "SNS notification was not "
        "delivered to verification SQS"
    )


def test_sqs_worker_dynamodb_sns_pipeline() -> None:
    sqs = get_sqs_client()
    sns = get_sns_client()
    dynamodb = get_dynamodb_client()

    ensure_idempotency_table()

    suffix = uuid4().hex[:8]

    inbound_queue_url = ""
    notification_queue_url = ""
    topic_arn = ""
    subscription_arn = ""

    risk_event = build_risk_event()

    event_id = str(
        risk_event.event_id
    )

    try:
        # Inbound queue consumed by Alert Worker.
        inbound_queue_url = (
            sqs.create_queue(
                QueueName=(
                    "realstock-alert-worker-"
                    f"{suffix}"
                )
            )["QueueUrl"]
        )

        # Verification queue subscribed to SNS.
        notification_queue_url = (
            sqs.create_queue(
                QueueName=(
                    "realstock-notification-"
                    f"{suffix}"
                )
            )["QueueUrl"]
        )

        notification_attributes = (
            sqs.get_queue_attributes(
                QueueUrl=(
                    notification_queue_url
                ),
                AttributeNames=[
                    "QueueArn"
                ],
            )
        )

        notification_queue_arn = (
            notification_attributes[
                "Attributes"
            ]["QueueArn"]
        )

        # SNS topic.
        topic_arn = (
            sns.create_topic(
                Name=(
                    "realstock-risk-alerts-"
                    f"{suffix}"
                )
            )["TopicArn"]
        )

        # SNS requires permission to send to SQS.
        queue_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid":
                        "AllowSnsSendMessage",
                    "Effect":
                        "Allow",
                    "Principal": {
                        "Service":
                            "sns.amazonaws.com"
                    },
                    "Action":
                        "sqs:SendMessage",
                    "Resource":
                        notification_queue_arn,
                    "Condition": {
                        "ArnEquals": {
                            "aws:SourceArn":
                                topic_arn
                        }
                    },
                }
            ],
        }

        sqs.set_queue_attributes(
            QueueUrl=notification_queue_url,
            Attributes={
                "Policy": json.dumps(
                    queue_policy
                )
            },
        )

        subscription = sns.subscribe(
            TopicArn=topic_arn,
            Protocol="sqs",
            Endpoint=notification_queue_arn,
            Attributes={
                "RawMessageDelivery":
                    "true"
            },
            ReturnSubscriptionArn=True,
        )

        subscription_arn = (
            subscription[
                "SubscriptionArn"
            ]
        )

        # Real DynamoDB idempotency store.
        idempotency_store = (
            DynamoDbIdempotencyStore(
                table_name=TABLE_NAME,
                processing_lease_seconds=60,
                completed_retention_seconds=3600,
                client=dynamodb,
            )
        )

        # Real SNS publisher.
        notification_publisher = (
            SnsRiskNotificationPublisher(
                topic_arn=topic_arn,
                client=sns,
            )
        )

        worker_service = (
            AlertWorkerService(
                parser=(
                    AlertMessageParser()
                ),
                idempotency_store=(
                    idempotency_store
                ),
                notification_publisher=(
                    notification_publisher
                ),
            )
        )

        consumer = SqsAlertConsumer(
            queue_url=inbound_queue_url,
            worker_service=worker_service,
            wait_time_seconds=1,
            client=sqs,
        )

        # -------------------------------------------------
        # First delivery
        # -------------------------------------------------

        body = build_eventbridge_body(
            risk_event
        )

        sqs.send_message(
            QueueUrl=inbound_queue_url,
            MessageBody=body,
        )

        first_result = (
            consumer.poll_once()
        )

        assert first_result is not None

        assert (
            first_result.status
            == AlertProcessingStatus.PUBLISHED
        )

        assert (
            first_result.event_id
            == event_id
        )

        assert (
            first_result
            .notification_message_id
        )

        # Worker must ACK the inbound message.
        inbound_after = (
            sqs.receive_message(
                QueueUrl=inbound_queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=1,
            )
        )

        assert not inbound_after.get(
            "Messages"
        )

        # -------------------------------------------------
        # Verify SNS actually delivered the notification.
        # -------------------------------------------------

        notification_message = (
            receive_notification(
                client=sqs,
                queue_url=(
                    notification_queue_url
                ),
            )
        )

        notification_body = json.loads(
            notification_message["Body"]
        )

        assert (
            notification_body[
                "notification_type"
            ]
            == "risk_alert"
        )

        assert (
            notification_body["event_id"]
            == event_id
        )

        assert (
            notification_body["severity"]
            == "CRITICAL"
        )

        assert (
            notification_body["market"]
            == "US"
        )

        assert (
            notification_body["symbol"]
            == "AAPL"
        )

        assert (
            Decimal(
                notification_body[
                    "observed_value"
                ]
            )
            == Decimal("-6")
        )

        sqs.delete_message(
            QueueUrl=(
                notification_queue_url
            ),
            ReceiptHandle=(
                notification_message[
                    "ReceiptHandle"
                ]
            ),
        )

        # -------------------------------------------------
        # DynamoDB must now be COMPLETED.
        # -------------------------------------------------

        status = (
            idempotency_store.get_status(
                event_id=event_id
            )
        )

        assert (
            status
            == IdempotencyStatus.COMPLETED
        )

        # -------------------------------------------------
        # Simulate at-least-once duplicate delivery.
        # -------------------------------------------------

        sqs.send_message(
            QueueUrl=inbound_queue_url,
            MessageBody=body,
        )

        duplicate_result = (
            consumer.poll_once()
        )

        assert (
            duplicate_result
            is not None
        )

        assert (
            duplicate_result.status
            == AlertProcessingStatus.DUPLICATE
        )

        # Duplicate must also be ACKed.
        inbound_duplicate_after = (
            sqs.receive_message(
                QueueUrl=inbound_queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=1,
            )
        )

        assert not (
            inbound_duplicate_after.get(
                "Messages"
            )
        )

        # Critical idempotency assertion:
        # duplicate processing must not publish SNS again.
        second_notification = (
            sqs.receive_message(
                QueueUrl=(
                    notification_queue_url
                ),
                MaxNumberOfMessages=1,
                WaitTimeSeconds=2,
            )
        )

        assert not (
            second_notification.get(
                "Messages"
            )
        )

    finally:
        try:
            dynamodb.delete_item(
                TableName=TABLE_NAME,
                Key={
                    "event_id": {
                        "S": event_id,
                    }
                },
            )
        except Exception:
            pass

        if subscription_arn:
            try:
                sns.unsubscribe(
                    SubscriptionArn=(
                        subscription_arn
                    )
                )
            except Exception:
                pass

        if topic_arn:
            try:
                sns.delete_topic(
                    TopicArn=topic_arn
                )
            except Exception:
                pass

        if inbound_queue_url:
            try:
                sqs.delete_queue(
                    QueueUrl=(
                        inbound_queue_url
                    )
                )
            except Exception:
                pass

        if notification_queue_url:
            try:
                sqs.delete_queue(
                    QueueUrl=(
                        notification_queue_url
                    )
                )
            except Exception:
                pass