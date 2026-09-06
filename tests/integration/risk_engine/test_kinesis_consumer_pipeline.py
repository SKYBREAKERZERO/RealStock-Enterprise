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
    get_eventbridge_client,
    get_kinesis_client,
    get_sqs_client,
)
from libs.domain.market import (
    Market,
    MarketQuote,
)
from libs.events import (
    create_market_quote_event,
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
    10,
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
        f"Kinesis stream did not become ACTIVE: "
        f"{stream_name}"
    )


def receive_risk_message(
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
        "risk event was not delivered "
        "to SQS"
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
        response = client.get_records(
            ShardIterator=iterator,
            Limit=100,
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


def test_kinesis_records_generate_risk_event_and_route_to_sqs() -> None:
    kinesis = get_kinesis_client()
    eventbridge = (
        get_eventbridge_client()
    )
    sqs = get_sqs_client()

    suffix = uuid4().hex[:8]

    stream_name = (
        f"realstock-risk-kinesis-"
        f"{suffix}"
    )

    queue_name = (
        f"realstock-risk-output-"
        f"{suffix}"
    )

    rule_name = (
        f"realstock-risk-rule-"
        f"{suffix}"
    )

    queue_url = ""

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

        shard_id = shards[0][
            "ShardId"
        ]

        # Create iterator before publishing so this test
        # only consumes its own newly produced records.
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
        # EventBridge -> SQS
        # ==================================================

        queue_url = sqs.create_queue(
            QueueName=queue_name
        )["QueueUrl"]

        attributes = (
            sqs.get_queue_attributes(
                QueueUrl=queue_url,
                AttributeNames=[
                    "QueueArn"
                ],
            )
        )

        queue_arn = attributes[
            "Attributes"
        ]["QueueArn"]

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

        queue_policy = {
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
                        queue_arn
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
                        "Id": (
                            "risk-output"
                        ),
                        "Arn": queue_arn,
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

        # ==================================================
        # Application components
        # ==================================================

        producer = (
            KinesisMarketEventProducer(
                stream_name=stream_name
            )
        )

        state_store = (
            InMemoryQuoteStateStore()
        )

        risk_engine = (
            RiskEngineService(
                state_store=state_store
            )
        )

        risk_publisher = (
            EventBridgeRiskEventPublisher()
        )

        consumer = (
            KinesisRiskEngineConsumer(
                risk_engine=risk_engine,
                publisher=risk_publisher,
            )
        )

        # ==================================================
        # Produce two market events
        #
        # 100 -> 94 = -6%
        # ==================================================

        first_event = (
            build_quote_event(
                price=Decimal("100"),
                seconds=1,
            )
        )

        second_event = (
            build_quote_event(
                price=Decimal("94"),
                seconds=2,
            )
        )

        producer.publish(
            first_event,
            partition_key="AAPL",
        )

        producer.publish(
            second_event,
            partition_key="AAPL",
        )

        # ==================================================
        # Real Kinesis read
        # ==================================================

        records = (
            read_kinesis_records(
                client=kinesis,
                shard_iterator=(
                    shard_iterator
                ),
                expected_count=2,
            )
        )

        assert len(records) == 2

        # ==================================================
        # Kinesis -> RiskEngine
        # ==================================================

        first_result = (
            consumer.process_record(
                records[0]
            )
        )

        assert (
            first_result.market_event_id
            == str(first_event.event_id)
        )

        assert (
            first_result.alert_generated
            is False
        )

        second_result = (
            consumer.process_record(
                records[1]
            )
        )

        assert (
            second_result.market_event_id
            == str(second_event.event_id)
        )

        assert (
            second_result.alert_generated
            is True
        )

        assert (
            second_result.risk_event_id
            is not None
        )

        assert (
            second_result
            .eventbridge_event_id
            is not None
        )

        # ==================================================
        # EventBridge -> SQS
        # ==================================================

        message = receive_risk_message(
            client=sqs,
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
            == second_result.risk_event_id
        )

        # ==================================================
        # Trace continuity
        # ==================================================

        assert (
            detail["correlation_id"]
            == str(
                second_event.correlation_id
            )
        )

        assert (
            detail["causation_id"]
            == str(
                second_event.event_id
            )
        )

        # ==================================================
        # Risk business result
        # ==================================================

        payload = detail[
            "payload"
        ]

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
                payload[
                    "observed_value"
                ]
            )
            == Decimal("-6")
        )

        assert (
            Decimal(
                payload["threshold"]
            )
            == Decimal("5")
        )

        # ==================================================
        # Risk processing state
        # ==================================================

        latest_quote = (
            state_store.get_quote(
                market=Market.US,
                symbol="AAPL",
            )
        )

        assert latest_quote is not None

        assert (
            latest_quote.mid_price
            == Decimal("94")
        )

    finally:
        try:
            eventbridge.remove_targets(
                Rule=rule_name,
                EventBusName="default",
                Ids=[
                    "risk-output"
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

        try:
            kinesis.delete_stream(
                StreamName=stream_name,
                EnforceConsumerDeletion=True,
            )
        except Exception:
            pass