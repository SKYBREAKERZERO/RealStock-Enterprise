from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from libs.aws import (
    get_dynamodb_client,
    get_sqs_client,
)
from libs.domain.market import Market
from libs.domain.risk import (
    RiskAlert,
    RiskSeverity,
    RiskType,
)
from libs.events import create_risk_alert_event
from services.alert_worker import (
    DEFAULT_IDEMPOTENCY_TABLE_NAME,
    EVENTBRIDGE_RISK_SOURCE,
    AlertMessageParser,
    AlertProcessingStatus,
    AlertWorkerService,
    DynamoDbIdempotencyStore,
    IdempotencyStatus,
    SnsPublishResult,
    SqsAlertConsumer,
)

pytestmark = pytest.mark.integration

TABLE_NAME = DEFAULT_IDEMPOTENCY_TABLE_NAME


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
            16,
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
    return json.dumps(
        {
            "version": "0",
            "id": str(uuid4()),
            "detail-type":
                "risk.alert.detected",
            "source":
                EVENTBRIDGE_RISK_SOURCE,
            "account":
                "000000000000",
            "time":
                "2026-09-05T16:00:00Z",
            "region":
                "ap-northeast-1",
            "resources": [],
            "detail":
                risk_event.to_event_dict(),
        }
    )


class FlakyNotificationPublisher:
    """
    First notification attempt fails.
    The second succeeds.
    """

    def __init__(self) -> None:
        self.calls = 0

    def publish(
        self,
        event,
    ) -> SnsPublishResult:
        self.calls += 1

        if self.calls == 1:
            raise RuntimeError(
                "simulated SNS outage"
            )

        return SnsPublishResult(
            message_id=(
                "sns-retry-success"
            )
        )


def test_sns_failure_releases_claim_and_sqs_retry_succeeds() -> None:
    sqs = get_sqs_client()
    dynamodb = get_dynamodb_client()

    ensure_idempotency_table()

    suffix = uuid4().hex[:8]
    queue_url = ""

    risk_event = build_risk_event()
    event_id = str(
        risk_event.event_id
    )

    try:
        queue_url = sqs.create_queue(
            QueueName=(
                "realstock-retry-"
                f"{suffix}"
            ),
            Attributes={
                "VisibilityTimeout": "1",
            },
        )["QueueUrl"]

        store = (
            DynamoDbIdempotencyStore(
                table_name=TABLE_NAME,
                processing_lease_seconds=30,
                completed_retention_seconds=3600,
                client=dynamodb,
            )
        )

        publisher = (
            FlakyNotificationPublisher()
        )

        worker = AlertWorkerService(
            parser=AlertMessageParser(),
            idempotency_store=store,
            notification_publisher=publisher,
        )

        consumer = SqsAlertConsumer(
            queue_url=queue_url,
            worker_service=worker,
            wait_time_seconds=1,
            client=sqs,
        )

        sqs.send_message(
            QueueUrl=queue_url,
            MessageBody=(
                build_eventbridge_body(
                    risk_event
                )
            ),
        )

        # Attempt 1:
        # SNS fails, therefore the SQS message
        # must remain unacknowledged.
        with pytest.raises(
            RuntimeError,
            match="simulated SNS outage",
        ):
            consumer.poll_once()

        assert publisher.calls == 1

        # Failed downstream delivery must release
        # the DynamoDB processing claim.
        assert (
            store.get_status(
                event_id=event_id
            )
            is None
        )

        time.sleep(1.25)

        # Attempt 2:
        # same SQS message becomes visible again.
        second_result = (
            consumer.poll_once()
        )

        assert second_result is not None

        assert (
            second_result.status
            == AlertProcessingStatus.PUBLISHED
        )

        assert (
            second_result.event_id
            == event_id
        )

        assert (
            second_result
            .notification_message_id
            == "sns-retry-success"
        )

        assert publisher.calls == 2

        assert (
            store.get_status(
                event_id=event_id
            )
            == IdempotencyStatus.COMPLETED
        )

        # Successful retry must ACK/delete
        # the SQS message.
        after_success = (
            sqs.receive_message(
                QueueUrl=queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=1,
            )
        )

        assert not after_success.get(
            "Messages"
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

        if queue_url:
            try:
                sqs.delete_queue(
                    QueueUrl=queue_url
                )
            except Exception:
                pass


def receive_dlq_message(
    *,
    sqs,
    queue_url: str,
) -> dict:
    for _ in range(12):
        response = (
            sqs.receive_message(
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
        "poison message was not "
        "redriven to DLQ"
    )


def test_poison_message_is_redriven_to_dlq() -> None:
    sqs = get_sqs_client()

    suffix = uuid4().hex[:8]

    source_queue_url = ""
    dlq_url = ""

    try:
        # Create DLQ.
        dlq_url = sqs.create_queue(
            QueueName=(
                "realstock-alert-dlq-"
                f"{suffix}"
            )
        )["QueueUrl"]

        dlq_arn = (
            sqs.get_queue_attributes(
                QueueUrl=dlq_url,
                AttributeNames=[
                    "QueueArn"
                ],
            )["Attributes"]["QueueArn"]
        )

        # Source queue:
        # after two failed receives,
        # SQS should redrive the poison message.
        source_queue_url = (
            sqs.create_queue(
                QueueName=(
                    "realstock-alert-source-"
                    f"{suffix}"
                ),
                Attributes={
                    "VisibilityTimeout":
                        "1",
                    "RedrivePolicy":
                        json.dumps(
                            {
                                "deadLetterTargetArn":
                                    dlq_arn,
                                "maxReceiveCount":
                                    "2",
                            }
                        ),
                },
            )["QueueUrl"]
        )

        store = (
            DynamoDbIdempotencyStore(
                table_name=TABLE_NAME,
                client=(
                    get_dynamodb_client()
                ),
            )
        )

        publisher = (
            FlakyNotificationPublisher()
        )

        worker = AlertWorkerService(
            parser=AlertMessageParser(),
            idempotency_store=store,
            notification_publisher=publisher,
        )

        consumer = SqsAlertConsumer(
            queue_url=source_queue_url,
            worker_service=worker,
            wait_time_seconds=1,
            client=sqs,
        )

        # Invalid JSON:
        # parser fails before DynamoDB or SNS.
        sqs.send_message(
            QueueUrl=source_queue_url,
            MessageBody="{broken",
        )

        with pytest.raises(
            ValueError
        ):
            consumer.poll_once()

        time.sleep(1.25)

        with pytest.raises(
            ValueError
        ):
            consumer.poll_once()

        time.sleep(1.25)

        # One additional poll allows the queue
        # implementation to evaluate redrive.
        try:
            consumer.poll_once()
        except ValueError:
            pass

        dlq_message = (
            receive_dlq_message(
                sqs=sqs,
                queue_url=dlq_url,
            )
        )

        assert (
            dlq_message["Body"]
            == "{broken"
        )

        # Parser failure happens before business
        # side effects.
        assert publisher.calls == 0

        sqs.delete_message(
            QueueUrl=dlq_url,
            ReceiptHandle=(
                dlq_message[
                    "ReceiptHandle"
                ]
            ),
        )

    finally:
        if source_queue_url:
            try:
                sqs.delete_queue(
                    QueueUrl=(
                        source_queue_url
                    )
                )
            except Exception:
                pass

        if dlq_url:
            try:
                sqs.delete_queue(
                    QueueUrl=dlq_url
                )
            except Exception:
                pass