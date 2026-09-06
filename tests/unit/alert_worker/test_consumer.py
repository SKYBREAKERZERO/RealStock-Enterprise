from __future__ import annotations

import logging
from unittest.mock import Mock

import pytest

from libs.observability import (
    InMemoryMetricSink,
    MetricsRecorder,
)
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
    metrics: MetricsRecorder | None = None,
) -> SqsAlertConsumer:
    return SqsAlertConsumer(
        queue_url=QUEUE_URL,
        worker_service=service,
        wait_time_seconds=0,
        client=client,
        metrics=metrics,
    )


def build_message() -> dict:
    return {
        "MessageId": "sqs-001",
        "ReceiptHandle": "receipt-001",
        "Body": "{}",
    }


# =========================================================
# Functional behavior
# =========================================================


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


# =========================================================
# Structured logging
# =========================================================


def test_published_ack_is_logged(
    caplog,
) -> None:
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

    with caplog.at_level(
        logging.INFO,
        logger=(
            "realstock."
            "alert_worker.consumer"
        ),
    ):
        consumer.poll_once()

    record = next(
        record
        for record in caplog.records
        if (
            record.getMessage()
            == (
                "sqs alert message "
                "acknowledged"
            )
        )
    )

    fields = record.structured_fields

    assert (
        fields["sqs_message_id"]
        == "sqs-001"
    )

    assert (
        fields["event_id"]
        == "risk-event-001"
    )

    assert (
        fields["processing_status"]
        == "PUBLISHED"
    )

    assert (
        fields["acknowledged"]
        is True
    )


def test_duplicate_ack_is_logged(
    caplog,
) -> None:
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

    with caplog.at_level(
        logging.INFO,
        logger=(
            "realstock."
            "alert_worker.consumer"
        ),
    ):
        consumer.poll_once()

    record = next(
        record
        for record in caplog.records
        if (
            record.getMessage()
            == (
                "sqs alert message "
                "acknowledged"
            )
        )
    )

    fields = record.structured_fields

    assert (
        fields["processing_status"]
        == "DUPLICATE"
    )

    assert (
        fields["acknowledged"]
        is True
    )


def test_in_progress_no_ack_is_logged(
    caplog,
) -> None:
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

    with caplog.at_level(
        logging.INFO,
        logger=(
            "realstock."
            "alert_worker.consumer"
        ),
    ):
        consumer.poll_once()

    record = next(
        record
        for record in caplog.records
        if (
            record.getMessage()
            == (
                "sqs alert message left "
                "unacknowledged"
            )
        )
    )

    fields = record.structured_fields

    assert (
        fields["processing_status"]
        == "IN_PROGRESS"
    )

    assert (
        fields["acknowledged"]
        is False
    )

    client.delete_message.assert_not_called()


def test_processing_failure_no_ack_is_logged(
    caplog,
) -> None:
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

    with caplog.at_level(
        logging.ERROR,
        logger=(
            "realstock."
            "alert_worker.consumer"
        ),
    ):
        with pytest.raises(
            RuntimeError,
            match="processing failed",
        ):
            consumer.poll_once()

    record = next(
        record
        for record in caplog.records
        if (
            record.getMessage()
            == (
                "alert message processing "
                "failed; message not "
                "acknowledged"
            )
        )
    )

    assert (
        record.levelno
        == logging.ERROR
    )

    assert (
        record.exc_info
        is not None
    )

    fields = record.structured_fields

    assert (
        fields["sqs_message_id"]
        == "sqs-001"
    )

    client.delete_message.assert_not_called()


# =========================================================
# Metrics
# =========================================================


def test_published_metrics_record_receive_and_ack() -> None:
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
                AlertProcessingStatus.PUBLISHED
            ),
            event_id="risk-event-001",
            notification_message_id="sns-001",
        )
    )

    sink = InMemoryMetricSink()

    consumer = build_consumer(
        client=client,
        service=service,
        metrics=MetricsRecorder(
            sink=sink
        ),
    )

    consumer.poll_once()

    names = [
        metric.name
        for metric in sink.metrics
    ]

    assert (
        "SqsMessagesReceived"
        in names
    )

    assert (
        "SqsMessagesAcknowledged"
        in names
    )

    assert (
        "SqsMessagesNotAcknowledged"
        not in names
    )

    assert (
        "SqsProcessingFailures"
        not in names
    )

    acknowledged = next(
        metric
        for metric in sink.metrics
        if (
            metric.name
            == "SqsMessagesAcknowledged"
        )
    )

    assert (
        acknowledged.dimensions
        == {
            "ProcessingStatus": "PUBLISHED"
        }
    )


def test_duplicate_metrics_record_ack_status() -> None:
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

    sink = InMemoryMetricSink()

    consumer = build_consumer(
        client=client,
        service=service,
        metrics=MetricsRecorder(
            sink=sink
        ),
    )

    consumer.poll_once()

    acknowledged = next(
        metric
        for metric in sink.metrics
        if (
            metric.name
            == "SqsMessagesAcknowledged"
        )
    )

    assert (
        acknowledged.dimensions
        == {
            "ProcessingStatus": "DUPLICATE"
        }
    )

    assert (
        "SqsProcessingFailures"
        not in {
            metric.name
            for metric in sink.metrics
        }
    )


def test_in_progress_metrics_record_no_ack() -> None:
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

    sink = InMemoryMetricSink()

    consumer = build_consumer(
        client=client,
        service=service,
        metrics=MetricsRecorder(
            sink=sink
        ),
    )

    consumer.poll_once()

    not_acknowledged = next(
        metric
        for metric in sink.metrics
        if (
            metric.name
            == "SqsMessagesNotAcknowledged"
        )
    )

    assert (
        not_acknowledged.dimensions
        == {
            "Reason": "IN_PROGRESS"
        }
    )

    assert (
        "SqsMessagesAcknowledged"
        not in {
            metric.name
            for metric in sink.metrics
        }
    )


def test_processing_failure_metrics_record_failure() -> None:
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

    sink = InMemoryMetricSink()

    consumer = build_consumer(
        client=client,
        service=service,
        metrics=MetricsRecorder(
            sink=sink
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="processing failed",
    ):
        consumer.poll_once()

    names = [
        metric.name
        for metric in sink.metrics
    ]

    assert (
        "SqsMessagesReceived"
        in names
    )

    assert (
        "SqsMessagesNotAcknowledged"
        in names
    )

    assert (
        "SqsProcessingFailures"
        in names
    )

    assert (
        "SqsMessagesAcknowledged"
        not in names
    )

    failure = next(
        metric
        for metric in sink.metrics
        if (
            metric.name
            == "SqsProcessingFailures"
        )
    )

    assert (
        failure.dimensions
        == {
            "FailureStage": "WORKER"
        }
    )


def test_ack_failure_is_not_counted_as_acknowledged() -> None:
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
                AlertProcessingStatus.PUBLISHED
            ),
            event_id="risk-event-001",
            notification_message_id="sns-001",
        )
    )

    client.delete_message.side_effect = (
        RuntimeError(
            "SQS delete failed"
        )
    )

    sink = InMemoryMetricSink()

    consumer = build_consumer(
        client=client,
        service=service,
        metrics=MetricsRecorder(
            sink=sink
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="SQS delete failed",
    ):
        consumer.poll_once()

    names = [
        metric.name
        for metric in sink.metrics
    ]

    assert (
        "SqsMessagesReceived"
        in names
    )

    assert (
        "SqsMessagesNotAcknowledged"
        in names
    )

    assert (
        "SqsProcessingFailures"
        in names
    )

    assert (
        "SqsMessagesAcknowledged"
        not in names
    )

    not_acknowledged = next(
        metric
        for metric in sink.metrics
        if (
            metric.name
            == "SqsMessagesNotAcknowledged"
        )
    )

    assert (
        not_acknowledged.dimensions
        == {
            "Reason": "ACK_FAILURE"
        }
    )

    failure = next(
        metric
        for metric in sink.metrics
        if (
            metric.name
            == "SqsProcessingFailures"
        )
    )

    assert (
        failure.dimensions
        == {
            "FailureStage": "ACK"
        }
    )