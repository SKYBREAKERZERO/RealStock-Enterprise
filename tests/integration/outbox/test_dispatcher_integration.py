from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

import libs.database.models.outbox as outbox_models
from libs.aws import (
    get_eventbridge_client,
    get_sqs_client,
)
from libs.database.repositories.outbox import (
    OutboxRepository,
)
from libs.database.session import (
    get_session_factory,
)
from libs.events.envelope import EventEnvelope
from services.outbox_dispatcher.dispatcher import (
    OutboxDispatcher,
)
from services.outbox_dispatcher.publisher import (
    EventBridgeOutboxPublisher,
)

pytestmark = pytest.mark.integration


TEST_OCCURRED_AT = datetime(
    2000,
    1,
    1,
    0,
    0,
    tzinfo=UTC,
)


def _receive_message(
    *,
    sqs_client,
    queue_url: str,
) -> dict[str, object]:
    """
    Wait for one EventBridge-delivered SQS message.
    """

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

        time.sleep(
            0.25
        )

    raise AssertionError(
        "outbox event was not delivered to SQS"
    )


def test_dispatcher_publishes_outbox_event_and_marks_it_published() -> None:
    """
    Verify the complete transactional outbox dispatch path:

        PostgreSQL
            ↓
        claim + lease
            ↓
        commit claim transaction
            ↓
        LocalStack EventBridge
            ↓
        SQS target
            ↓
        mark_published
            ↓
        PostgreSQL commit
    """

    eventbridge = (
        get_eventbridge_client()
    )

    sqs = get_sqs_client()

    session_factory = (
        get_session_factory()
    )

    suffix = uuid4().hex[:8]

    queue_name = (
        f"realstock-outbox-{suffix}"
    )

    rule_name = (
        f"realstock-outbox-rule-{suffix}"
    )

    worker_id = (
        f"outbox-test-worker-{suffix}"
    )

    queue_url = ""

    event = EventEnvelope[
        dict[str, object]
    ](
        event_type="portfolio.created",
        schema_version=1,
        occurred_at=TEST_OCCURRED_AT,
        source="portfolio-api",
        payload={
            "portfolio_id": str(
                uuid4()
            ),
            "user_id": (
                f"integration-user-{suffix}"
            ),
            "name": (
                "Integration Portfolio"
            ),
            "currency": "USD",
        },
    )

    try:
        # ======================================================
        # Arrange EventBridge -> SQS target
        # ======================================================

        queue_response = (
            sqs.create_queue(
                QueueName=queue_name
            )
        )

        queue_url = (
            queue_response[
                "QueueUrl"
            ]
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
            ][
                "QueueArn"
            ]
        )

        event_pattern = {
            "source": [
                "realstock.portfolio-api"
            ],
            "detail-type": [
                "portfolio.created"
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
                        "AllowEventBridgeSendMessage"
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
                    "Resource": queue_arn,
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
                            "outbox-integration-sqs"
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

        # ======================================================
        # Arrange PostgreSQL outbox event
        # ======================================================

        with session_factory() as session:
            repository = (
                OutboxRepository(
                    session
                )
            )

            repository.add_event(
                aggregate_type="portfolio",
                aggregate_id=(
                    event.payload[
                        "portfolio_id"
                    ]
                ),
                event=event,
            )

            session.commit()

        # ======================================================
        # Act
        # ======================================================

        publisher = (
            EventBridgeOutboxPublisher(
                client=eventbridge
            )
        )

        dispatcher = (
            OutboxDispatcher(
                session_factory=(
                    session_factory
                ),
                publisher=publisher,
                worker_id=worker_id,
                batch_size=1,
                lease_seconds=60,
            )
        )

        dispatch_result = (
            dispatcher.dispatch_once(
                now=datetime.now(
                    UTC
                )
            )
        )

        # ======================================================
        # Assert dispatcher result
        # ======================================================

        assert (
            dispatch_result.claimed
            == 1
        )

        assert (
            dispatch_result.published
            == 1
        )

        assert (
            dispatch_result.failed
            == 0
        )

        # ======================================================
        # Assert PostgreSQL acknowledgement
        # ======================================================

        with session_factory() as session:
            statement = (
                select(
                    outbox_models.OutboxEventModel
                )
                .where(
                    outbox_models
                    .OutboxEventModel
                    .event_id
                    == event.event_id
                )
            )

            stored_event = (
                session
                .execute(statement)
                .scalar_one()
            )

            assert (
                stored_event.published_at
                is not None
            )

            assert (
                stored_event.locked_by
                is None
            )

            assert (
                stored_event.locked_until
                is None
            )

            assert (
                stored_event.last_error
                is None
            )

            assert (
                stored_event.attempt_count
                == 0
            )

        # ======================================================
        # Assert EventBridge -> SQS delivery
        # ======================================================

        message = _receive_message(
            sqs_client=sqs,
            queue_url=queue_url,
        )

        outer_event = json.loads(
            message[
                "Body"
            ]
        )

        assert (
            outer_event[
                "source"
            ]
            == "realstock.portfolio-api"
        )

        assert (
            outer_event[
                "detail-type"
            ]
            == "portfolio.created"
        )

        detail = (
            outer_event[
                "detail"
            ]
        )

        assert (
            detail[
                "event_id"
            ]
            == str(
                event.event_id
            )
        )

        assert (
            detail[
                "event_type"
            ]
            == event.event_type
        )

        assert (
            detail[
                "schema_version"
            ]
            == event.schema_version
        )

        assert (
            detail[
                "source"
            ]
            == event.source
        )

        assert (
            detail[
                "correlation_id"
            ]
            == str(
                event.correlation_id
            )
        )

        assert (
            detail[
                "payload"
            ]
            == event.payload
        )

    finally:
        # ======================================================
        # PostgreSQL cleanup
        # ======================================================

        try:
            with session_factory() as session:
                session.execute(
                    delete(
                        outbox_models
                        .OutboxEventModel
                    )
                    .where(
                        outbox_models
                        .OutboxEventModel
                        .event_id
                        == event.event_id
                    )
                )

                session.commit()

        except Exception:
            pass

        # ======================================================
        # EventBridge cleanup
        # ======================================================

        try:
            eventbridge.remove_targets(
                Rule=rule_name,
                EventBusName="default",
                Ids=[
                    "outbox-integration-sqs"
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

        # ======================================================
        # SQS cleanup
        # ======================================================

        if queue_url:
            try:
                sqs.delete_queue(
                    QueueUrl=queue_url
                )

            except Exception:
                pass