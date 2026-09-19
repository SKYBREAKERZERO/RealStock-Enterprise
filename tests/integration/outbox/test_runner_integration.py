from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from threading import Thread
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
from services.outbox_dispatcher.metrics import (
    NoOpOutboxMetrics,
)
from services.outbox_dispatcher.publisher import (
    EventBridgeOutboxPublisher,
)
from services.outbox_dispatcher.runner import (
    OutboxRunner,
)

pytestmark = pytest.mark.integration


def _wait_until_published(
    *,
    session_factory,
    event_id,
    timeout_seconds: float = 10.0,
) -> None:
    """
    Wait until the runner marks the requested outbox event
    as published.
    """

    deadline = (
        time.monotonic()
        + timeout_seconds
    )

    while (
        time.monotonic()
        < deadline
    ):
        with session_factory() as session:
            statement = (
                select(
                    outbox_models
                    .OutboxEventModel
                )
                .where(
                    outbox_models
                    .OutboxEventModel
                    .event_id
                    == event_id
                )
            )

            stored_event = (
                session
                .execute(statement)
                .scalar_one_or_none()
            )

            if (
                stored_event is not None
                and stored_event.published_at
                is not None
            ):
                return

        time.sleep(
            0.1
        )

    raise AssertionError(
        "outbox event was not published "
        "before timeout"
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
        "runner-dispatched event was not "
        "delivered to SQS"
    )


def test_runner_automatically_dispatches_event_and_stops_cleanly() -> None:
    """
    Verify the complete long-running outbox worker path:

        PostgreSQL
            ↓
        OutboxRunner polling loop
            ↓
        OutboxDispatcher
            ↓
        EventBridge
            ↓
        SQS
            ↓
        database acknowledgement
            ↓
        graceful runner shutdown
    """

    eventbridge = (
        get_eventbridge_client()
    )

    sqs = (
        get_sqs_client()
    )

    session_factory = (
        get_session_factory()
    )

    suffix = uuid4().hex[:8]

    queue_name = (
        f"realstock-runner-{suffix}"
    )

    rule_name = (
        f"realstock-runner-rule-{suffix}"
    )

    worker_id = (
        f"runner-integration-{suffix}"
    )

    event_type = (
        f"test.outbox.runner.{suffix}"
    )

    event_source = (
        f"runner-integration-{suffix}"
    )

    queue_url = ""

    runner: OutboxRunner | None = None
    worker_thread: Thread | None = None

    worker_errors: list[
        BaseException
    ] = []

    event = EventEnvelope[
        dict[str, object]
    ](
        event_type=event_type,
        schema_version=1,
        occurred_at=datetime.now(
            UTC
        ),
        source=event_source,
        payload={
            "integration_test": True,
            "test_id": suffix,
        },
    )

    try:
        # ======================================================
        # Arrange EventBridge -> SQS
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
                f"realstock.{event_source}"
            ],
            "detail-type": [
                event_type
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
                            "runner-integration-sqs"
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
        # Arrange PostgreSQL event
        # ======================================================

        with session_factory() as session:
            repository = (
                OutboxRepository(
                    session
                )
            )

            repository.add_event(
                aggregate_type="integration-test",
                aggregate_id=suffix,
                event=event,
            )

            session.commit()

        # ======================================================
        # Build real worker runtime
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
                lease_seconds=30,
            )
        )

        def backlog_snapshot_provider():
            with session_factory() as session:
                repository = (
                    OutboxRepository(
                        session
                    )
                )

                return (
                    repository
                    .get_backlog_snapshot()
                )

        runner = (
            OutboxRunner(
                dispatcher=dispatcher,
                backlog_snapshot_provider=(
                    backlog_snapshot_provider
                ),
                metrics=NoOpOutboxMetrics(),
                poll_interval_seconds=0.1,
                error_backoff_seconds=0.1,
                metrics_interval_seconds=1.0,
            )
        )

        def run_worker() -> None:
            try:
                runner.run_forever()

            except BaseException as exc:
                worker_errors.append(
                    exc
                )

        worker_thread = Thread(
            target=run_worker,
            name=(
                "outbox-runner-integration"
            ),
            daemon=True,
        )

        # ======================================================
        # Act
        # ======================================================

        worker_thread.start()

        _wait_until_published(
            session_factory=(
                session_factory
            ),
            event_id=event.event_id,
        )

        runner.request_stop()

        worker_thread.join(
            timeout=5.0
        )

        # ======================================================
        # Assert clean worker shutdown
        # ======================================================

        assert (
            not worker_thread.is_alive()
        )

        assert worker_errors == []

        # ======================================================
        # Assert PostgreSQL acknowledgement
        # ======================================================

        with session_factory() as session:
            statement = (
                select(
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
            == f"realstock.{event_source}"
        )

        assert (
            outer_event[
                "detail-type"
            ]
            == event_type
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
                "payload"
            ]
            == event.payload
        )

    finally:
        # ======================================================
        # Stop worker if assertion/setup failed early
        # ======================================================

        if runner is not None:
            try:
                runner.request_stop()
            except Exception:
                pass

        if (
            worker_thread is not None
            and worker_thread.is_alive()
        ):
            worker_thread.join(
                timeout=5.0
            )

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
                    "runner-integration-sqs"
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