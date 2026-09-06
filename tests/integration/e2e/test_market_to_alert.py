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
from botocore.exceptions import ClientError

from libs.aws import (
    get_dynamodb_client,
    get_eventbridge_client,
    get_kinesis_client,
    get_sns_client,
    get_sqs_client,
)
from libs.domain.market import (
    Market,
    MarketQuote,
)
from libs.events import (
    create_market_quote_event,
)
from services.alert_worker import (
    AlertMessageParser,
    AlertProcessingStatus,
    AlertWorkerService,
    DynamoDbIdempotencyStore,
    IdempotencyStatus,
    SnsRiskNotificationPublisher,
    SqsAlertConsumer,
)
from services.market_ingestor.producer import (
    KinesisMarketEventProducer,
)
from services.risk_engine import (
    EVENTBRIDGE_RISK_SOURCE,
    EventBridgeRiskEventPublisher,
    InMemoryQuoteStateStore,
    KinesisRiskEngineConsumer,
    RiskEngineService,
)

pytestmark = pytest.mark.integration


BASE_TIME = datetime(
    2026,
    9,
    6,
    11,
    0,
    tzinfo=UTC,
)


def build_quote_event(
    *,
    price: Decimal,
    seconds: int,
):
    quote = MarketQuote(
        symbol="AAPL",
        market=Market.US,
        bid_price=price,
        ask_price=price,
        bid_size=100,
        ask_size=100,
        timestamp=(
            BASE_TIME
            + timedelta(
                seconds=seconds
            )
        ),
    )

    return create_market_quote_event(
        quote
    )


def wait_for_stream_active(
    *,
    client,
    stream_name: str,
) -> None:
    for _ in range(40):
        try:
            response = (
                client.describe_stream_summary(
                    StreamName=stream_name
                )
            )

            status = response[
                "StreamDescriptionSummary"
            ]["StreamStatus"]

            if status == "ACTIVE":
                return

        except ClientError:
            pass

        time.sleep(0.25)

    raise AssertionError(
        "Kinesis stream did not become ACTIVE: "
        f"{stream_name}"
    )


def read_kinesis_records(
    *,
    client,
    shard_iterator: str,
    expected_count: int,
) -> list[dict]:
    records: list[dict] = []

    iterator = shard_iterator

    for _ in range(40):
        response = (
            client.get_records(
                ShardIterator=iterator,
                Limit=100,
            )
        )

        records.extend(
            response.get(
                "Records",
                [],
            )
        )

        next_iterator = (
            response.get(
                "NextShardIterator"
            )
        )

        if next_iterator:
            iterator = next_iterator

        if len(records) >= expected_count:
            return records

        time.sleep(0.25)

    return records


def poll_alert_worker(
    *,
    consumer: SqsAlertConsumer,
):
    for _ in range(20):
        result = consumer.poll_once()

        if result is not None:
            return result

        time.sleep(0.25)

    raise AssertionError(
        "Alert Worker did not receive "
        "risk event from SQS"
    )


def receive_notification(
    *,
    client,
    queue_url: str,
) -> dict:
    for _ in range(20):
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

        time.sleep(0.25)

    raise AssertionError(
        "SNS notification was not delivered"
    )


def test_market_event_to_risk_notification_full_pipeline() -> None:
    kinesis = get_kinesis_client()
    eventbridge = (
        get_eventbridge_client()
    )
    sqs = get_sqs_client()
    sns = get_sns_client()
    dynamodb = (
        get_dynamodb_client()
    )

    suffix = uuid4().hex[:8]

    stream_name = (
        f"realstock-e2e-market-"
        f"{suffix}"
    )

    inbound_queue_name = (
        f"realstock-e2e-risk-"
        f"{suffix}"
    )

    notification_queue_name = (
        f"realstock-e2e-notification-"
        f"{suffix}"
    )

    topic_name = (
        f"realstock-e2e-alerts-"
        f"{suffix}"
    )

    table_name = (
        f"realstock-e2e-idempotency-"
        f"{suffix}"
    )

    rule_name = (
        f"realstock-e2e-risk-rule-"
        f"{suffix}"
    )

    inbound_queue_url = ""
    notification_queue_url = ""
    topic_arn = ""
    subscription_arn = ""

    try:
        # ==================================================
        # Kinesis
        # ==================================================

        kinesis.create_stream(
            StreamName=stream_name,
            ShardCount=1,
        )

        wait_for_stream_active(
            client=kinesis,
            stream_name=stream_name,
        )

        shards = kinesis.list_shards(
            StreamName=stream_name
        )["Shards"]

        assert len(shards) == 1

        shard_id = (
            shards[0]["ShardId"]
        )

        iterator_response = (
            kinesis.get_shard_iterator(
                StreamName=stream_name,
                ShardId=shard_id,
                ShardIteratorType="LATEST",
            )
        )

        shard_iterator = (
            iterator_response[
                "ShardIterator"
            ]
        )

        # ==================================================
        # Alert Worker inbound SQS
        # ==================================================

        inbound_queue_url = (
            sqs.create_queue(
                QueueName=(
                    inbound_queue_name
                )
            )["QueueUrl"]
        )

        inbound_attributes = (
            sqs.get_queue_attributes(
                QueueUrl=inbound_queue_url,
                AttributeNames=[
                    "QueueArn"
                ],
            )
        )

        inbound_queue_arn = (
            inbound_attributes[
                "Attributes"
            ]["QueueArn"]
        )

        # ==================================================
        # EventBridge rule
        # ==================================================

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
            rule_response[
                "RuleArn"
            ]
        )

        inbound_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": (
                        "AllowEventBridge"
                        "SendMessage"
                    ),
                    "Effect": "Allow",
                    "Principal": {
                        "Service": (
                            "events.amazonaws.com"
                        )
                    },
                    "Action": (
                        "sqs:SendMessage"
                    ),
                    "Resource": (
                        inbound_queue_arn
                    ),
                    "Condition": {
                        "ArnEquals": {
                            "aws:SourceArn": (
                                rule_arn
                            )
                        }
                    },
                }
            ],
        }

        sqs.set_queue_attributes(
            QueueUrl=inbound_queue_url,
            Attributes={
                "Policy": json.dumps(
                    inbound_policy
                )
            },
        )

        target_response = (
            eventbridge.put_targets(
                Rule=rule_name,
                EventBusName="default",
                Targets=[
                    {
                        "Id": (
                            "alert-worker"
                        ),
                        "Arn": (
                            inbound_queue_arn
                        ),
                    }
                ],
            )
        )

        assert (
            target_response[
                "FailedEntryCount"
            ]
            == 0
        )

        # ==================================================
        # SNS verification queue
        # ==================================================

        notification_queue_url = (
            sqs.create_queue(
                QueueName=(
                    notification_queue_name
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

        topic_arn = (
            sns.create_topic(
                Name=topic_name
            )["TopicArn"]
        )

        notification_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": (
                        "AllowSnsSendMessage"
                    ),
                    "Effect": "Allow",
                    "Principal": {
                        "Service": (
                            "sns.amazonaws.com"
                        )
                    },
                    "Action": (
                        "sqs:SendMessage"
                    ),
                    "Resource": (
                        notification_queue_arn
                    ),
                    "Condition": {
                        "ArnEquals": {
                            "aws:SourceArn": (
                                topic_arn
                            )
                        }
                    },
                }
            ],
        }

        sqs.set_queue_attributes(
            QueueUrl=(
                notification_queue_url
            ),
            Attributes={
                "Policy": json.dumps(
                    notification_policy
                )
            },
        )

        subscription = (
            sns.subscribe(
                TopicArn=topic_arn,
                Protocol="sqs",
                Endpoint=(
                    notification_queue_arn
                ),
                Attributes={
                    "RawMessageDelivery":
                        "true"
                },
                ReturnSubscriptionArn=True,
            )
        )

        subscription_arn = (
            subscription[
                "SubscriptionArn"
            ]
        )

        # ==================================================
        # DynamoDB idempotency table
        # ==================================================

        dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {
                    "AttributeName":
                        "event_id",
                    "KeyType":
                        "HASH",
                }
            ],
            AttributeDefinitions=[
                {
                    "AttributeName":
                        "event_id",
                    "AttributeType":
                        "S",
                }
            ],
            BillingMode=(
                "PAY_PER_REQUEST"
            ),
        )

        dynamodb.get_waiter(
            "table_exists"
        ).wait(
            TableName=table_name
        )

        # ==================================================
        # Application components
        # ==================================================

        market_producer = (
            KinesisMarketEventProducer(
                stream_name=stream_name
            )
        )

        risk_state = (
            InMemoryQuoteStateStore()
        )

        risk_engine = (
            RiskEngineService(
                state_store=risk_state
            )
        )

        risk_publisher = (
            EventBridgeRiskEventPublisher(
                client=eventbridge
            )
        )

        risk_consumer = (
            KinesisRiskEngineConsumer(
                risk_engine=risk_engine,
                publisher=risk_publisher,
            )
        )

        idempotency_store = (
            DynamoDbIdempotencyStore(
                table_name=table_name,
                processing_lease_seconds=60,
                completed_retention_seconds=3600,
                client=dynamodb,
            )
        )

        notification_publisher = (
            SnsRiskNotificationPublisher(
                topic_arn=topic_arn,
                client=sns,
            )
        )

        worker_service = (
            AlertWorkerService(
                parser=AlertMessageParser(),
                idempotency_store=(
                    idempotency_store
                ),
                notification_publisher=(
                    notification_publisher
                ),
            )
        )

        alert_consumer = (
            SqsAlertConsumer(
                queue_url=(
                    inbound_queue_url
                ),
                worker_service=(
                    worker_service
                ),
                wait_time_seconds=1,
                client=sqs,
            )
        )

        # ==================================================
        # MARKET INPUT
        #
        # AAPL 100 -> 94 = -6%
        # ==================================================

        first_market_event = (
            build_quote_event(
                price=Decimal("100"),
                seconds=1,
            )
        )

        second_market_event = (
            build_quote_event(
                price=Decimal("94"),
                seconds=2,
            )
        )

        market_producer.publish(
            first_market_event,
            partition_key="AAPL",
        )

        market_producer.publish(
            second_market_event,
            partition_key="AAPL",
        )

        # ==================================================
        # Kinesis consume
        # ==================================================

        records = read_kinesis_records(
            client=kinesis,
            shard_iterator=(
                shard_iterator
            ),
            expected_count=2,
        )

        assert len(records) == 2

        first_risk_result = (
            risk_consumer.process_record(
                records[0]
            )
        )

        assert (
            first_risk_result
            .alert_generated
            is False
        )

        second_risk_result = (
            risk_consumer.process_record(
                records[1]
            )
        )

        assert (
            second_risk_result
            .alert_generated
            is True
        )

        assert (
            second_risk_result
            .risk_event_id
            is not None
        )

        risk_event_id = (
            second_risk_result
            .risk_event_id
        )

        # ==================================================
        # EventBridge -> SQS -> Alert Worker
        # ==================================================

        alert_result = (
            poll_alert_worker(
                consumer=alert_consumer
            )
        )

        assert (
            alert_result.status
            == AlertProcessingStatus.PUBLISHED
        )

        assert (
            alert_result.event_id
            == risk_event_id
        )

        assert (
            alert_result
            .notification_message_id
            is not None
        )

        # Successful processing must ACK
        # the inbound SQS message.
        inbound_after = (
            sqs.receive_message(
                QueueUrl=(
                    inbound_queue_url
                ),
                MaxNumberOfMessages=1,
                WaitTimeSeconds=1,
            )
        )

        assert not (
            inbound_after.get(
                "Messages"
            )
        )

        # ==================================================
        # DynamoDB idempotency
        # ==================================================

        status = (
            idempotency_store
            .get_status(
                event_id=risk_event_id
            )
        )

        assert (
            status
            == IdempotencyStatus.COMPLETED
        )

        # ==================================================
        # SNS final output
        # ==================================================

        notification_message = (
            receive_notification(
                client=sqs,
                queue_url=(
                    notification_queue_url
                ),
            )
        )

        notification = json.loads(
            notification_message["Body"]
        )

        assert (
            notification[
                "notification_type"
            ]
            == "risk_alert"
        )

        assert (
            notification[
                "event_id"
            ]
            == risk_event_id
        )

        assert (
            notification[
                "severity"
            ]
            == "CRITICAL"
        )

        assert (
            notification[
                "risk_type"
            ]
            == "PRICE_MOVE_PERCENT"
        )

        assert (
            notification[
                "market"
            ]
            == "US"
        )

        assert (
            notification[
                "symbol"
            ]
            == "AAPL"
        )

        assert (
            Decimal(
                notification[
                    "observed_value"
                ]
            )
            == Decimal("-6")
        )

        assert (
            Decimal(
                notification[
                    "threshold"
                ]
            )
            == Decimal("5")
        )

        # ==================================================
        # Distributed trace continuity
        # ==================================================

        assert (
            notification[
                "correlation_id"
            ]
            == str(
                second_market_event
                .correlation_id
            )
        )

        assert (
            notification[
                "causation_id"
            ]
            == str(
                second_market_event
                .event_id
            )
        )

        # ==================================================
        # ACK verification notification
        #
        # Delete the first SNS verification message before
        # replay checks. Otherwise the original message can
        # become visible again and look like a duplicate.
        # ==================================================

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

        # ==================================================
        # Risk state advanced
        # ==================================================

        latest_quote = (
            risk_state.get_quote(
                market=Market.US,
                symbol="AAPL",
            )
        )

        assert latest_quote is not None

        assert (
            latest_quote.mid_price
            == Decimal("94")
        )

        assert (
            latest_quote.timestamp
            == (
                BASE_TIME
                + timedelta(seconds=2)
            )
        )

        # ==================================================
        # PHASE 5
        # Kinesis replay semantics
        #
        # Simulate at-least-once reprocessing of the exact
        # same market record. Because the Risk Engine state
        # already contains the same timestamp, replay must
        # not create another risk alert.
        # ==================================================

        replay_result = (
            risk_consumer.process_record(
                records[1]
            )
        )

        assert (
            replay_result.market_event_id
            == str(
                second_market_event.event_id
            )
        )

        assert (
            replay_result.alert_generated
            is False
        )

        assert (
            replay_result.risk_event_id
            is None
        )

        assert (
            replay_result.eventbridge_event_id
            is None
        )

        # ==================================================
        # Risk state must remain unchanged after replay
        # ==================================================

        state_after_replay = (
            risk_state.get_quote(
                market=Market.US,
                symbol="AAPL",
            )
        )

        assert state_after_replay is not None

        assert (
            state_after_replay.mid_price
            == Decimal("94")
        )

        assert (
            state_after_replay.timestamp
            == (
                BASE_TIME
                + timedelta(seconds=2)
            )
        )

        # ==================================================
        # Replay must not create another EventBridge -> SQS
        # message for the Alert Worker.
        # ==================================================

        replay_inbound = (
            sqs.receive_message(
                QueueUrl=(
                    inbound_queue_url
                ),
                MaxNumberOfMessages=1,
                WaitTimeSeconds=2,
            )
        )

        assert not (
            replay_inbound.get(
                "Messages"
            )
        )

        # ==================================================
        # Replay must not create another SNS notification.
        # ==================================================

        replay_notification = (
            sqs.receive_message(
                QueueUrl=(
                    notification_queue_url
                ),
                MaxNumberOfMessages=1,
                WaitTimeSeconds=2,
            )
        )

        assert not (
            replay_notification.get(
                "Messages"
            )
        )

        # ==================================================
        # Downstream idempotency completion must remain stable
        # ==================================================

        replay_status = (
            idempotency_store.get_status(
                event_id=risk_event_id
            )
        )

        assert (
            replay_status
            == IdempotencyStatus.COMPLETED
        )

    finally:
        # ==================================================
        # Cleanup
        # ==================================================

        try:
            eventbridge.remove_targets(
                Rule=rule_name,
                EventBusName="default",
                Ids=[
                    "alert-worker"
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

        try:
            dynamodb.delete_table(
                TableName=table_name
            )
        except Exception:
            pass

        try:
            kinesis.delete_stream(
                StreamName=stream_name,
                EnforceConsumerDeletion=True,
            )
        except Exception:
            pass