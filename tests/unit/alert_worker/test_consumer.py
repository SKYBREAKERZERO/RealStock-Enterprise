from __future__ import annotations

from unittest.mock import Mock

import pytest

from services.alert_worker import (
    AlertProcessingResult,
    AlertProcessingStatus,
    SqsAlertConsumer,
)

pytestmark = pytest.mark.unit


QUEUE_URL = (
    "http://localhost:4566/"
    "000000000000/"
    "realstock-risk-alerts-test"
)


def build_consumer(
    *,
    client,
    service,
) -> SqsAlertConsumer:
    return SqsAlertConsumer(
        queue_url=QUEUE_URL,
        worker_service=service,
        wait_time_seconds=0,
        client=client,
    )


def build_message() -> dict:
    return {
        "MessageId": "sqs-001",
        "ReceiptHandle": "receipt-001",
        "Body": "{}",
    }


def test_poll_returns_none_when_queue_empty() -> None:
    client = Mock()
    service = Mock()

    client.receive_message.return_value = {}

    consumer = build_consumer(
        client=client,
        service=service,
    )

    result = consumer.poll_once()

    assert result is None

    service.process_message.assert_not_called()

    client.delete_message.assert_not_called()


def test_published_message_is_deleted() -> None:
    client = Mock()
    service = Mock()

    message = build_message()

    client.receive_message.return_value = {
        "Messages": [
            message
        ]
    }

    service.process_message.return_value = (
        AlertProcessingResult(
            status=(
                AlertProcessingStatus.PUBLISHED
            ),
            event_id="risk-event-001",
            notification_message_id="sns-001",
        )
    )

    consumer = build_consumer(
        client=client,
        service=service,
    )

    result = consumer.poll_once()

    assert result is not None

    assert (
        result.status
        == AlertProcessingStatus.PUBLISHED
    )

    client.delete_message.assert_called_once_with(
        QueueUrl=QUEUE_URL,
        ReceiptHandle="receipt-001",
    )


def test_duplicate_message_is_deleted() -> None:
    client = Mock()
    service = Mock()

    client.receive_message.return_value = {
        "Messages": [
            build_message()
        ]
    }

    service.process_message.return_value = (
        AlertProcessingResult(
            status=(
                AlertProcessingStatus.DUPLICATE
            ),
            event_id="risk-event-001",
        )
    )

    consumer = build_consumer(
        client=client,
        service=service,
    )

    result = consumer.poll_once()

    assert result is not None

    assert (
        result.status
        == AlertProcessingStatus.DUPLICATE
    )

    client.delete_message.assert_called_once()


def test_in_progress_message_is_not_deleted() -> None:
    client = Mock()
    service = Mock()

    client.receive_message.return_value = {
        "Messages": [
            build_message()
        ]
    }

    service.process_message.return_value = (
        AlertProcessingResult(
            status=(
                AlertProcessingStatus.IN_PROGRESS
            ),
            event_id="risk-event-001",
        )
    )

    consumer = build_consumer(
        client=client,
        service=service,
    )

    result = consumer.poll_once()

    assert result is not None

    assert (
        result.status
        == AlertProcessingStatus.IN_PROGRESS
    )

    client.delete_message.assert_not_called()


def test_processing_failure_does_not_delete_message() -> None:
    client = Mock()
    service = Mock()

    client.receive_message.return_value = {
        "Messages": [
            build_message()
        ]
    }

    service.process_message.side_effect = (
        RuntimeError(
            "processing failed"
        )
    )

    consumer = build_consumer(
        client=client,
        service=service,
    )

    with pytest.raises(
        RuntimeError,
        match="processing failed",
    ):
        consumer.poll_once()

    client.delete_message.assert_not_called()


def test_rejects_invalid_configuration() -> None:
    service = Mock()
    client = Mock()

    with pytest.raises(
        ValueError,
        match="queue_url",
    ):
        SqsAlertConsumer(
            queue_url=" ",
            worker_service=service,
            client=client,
        )

    with pytest.raises(
        ValueError,
        match="wait_time_seconds",
    ):
        SqsAlertConsumer(
            queue_url=QUEUE_URL,
            worker_service=service,
            wait_time_seconds=21,
            client=client,
        )