from __future__ import annotations

import json
import logging
from datetime import (
    UTC,
    datetime,
)
from decimal import Decimal
from unittest.mock import Mock

import pytest

from libs.domain.market import Market
from libs.domain.risk import (
    RiskAlert,
    RiskSeverity,
    RiskType,
)
from libs.events import (
    create_risk_alert_event,
)
from libs.observability import (
    InMemoryMetricSink,
    MetricsRecorder,
    MetricUnit,
)
from services.alert_worker import (
    EVENTBRIDGE_RISK_SOURCE,
    AlertMessageParser,
    AlertProcessingStatus,
    AlertWorkerService,
    IdempotencyClaim,
    IdempotencyStatus,
    InvalidAlertMessageError,
    SnsPublishResult,
)

pytestmark = pytest.mark.unit


def build_sqs_message():
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
            14,
            0,
            tzinfo=UTC,
        ),
    )

    event = create_risk_alert_event(
        alert
    )

    body = {
        "version": "0",
        "id": "eventbridge-001",
        "detail-type": (
            "risk.alert.detected"
        ),
        "source": (
            EVENTBRIDGE_RISK_SOURCE
        ),
        "account": (
            "000000000000"
        ),
        "time": (
            "2026-09-05T14:00:00Z"
        ),
        "region": (
            "ap-northeast-1"
        ),
        "resources": [],
        "detail": (
            event.to_event_dict()
        ),
    }

    message = {
        "MessageId": "sqs-001",
        "ReceiptHandle": (
            "receipt-001"
        ),
        "Body": json.dumps(
            body
        ),
    }

    return message, event


def build_service(
    *,
    store,
    publisher,
    metrics: MetricsRecorder | None = None,
):
    return AlertWorkerService(
        parser=AlertMessageParser(),
        idempotency_store=store,
        notification_publisher=publisher,
        metrics=metrics,
    )


# =========================================================
# Functional behavior
# =========================================================


def test_process_message_publishes_and_completes() -> None:
    store = Mock()
    publisher = Mock()

    message, event = (
        build_sqs_message()
    )

    claim = IdempotencyClaim(
        event_id=str(
            event.event_id
        ),
        claim_id="claim-001",
    )

    store.claim.return_value = claim

    publisher.publish.return_value = (
        SnsPublishResult(
            message_id="sns-001"
        )
    )

    service = build_service(
        store=store,
        publisher=publisher,
    )

    result = service.process_message(
        message
    )

    assert (
        result.status
        == AlertProcessingStatus.PUBLISHED
    )

    assert (
        result.event_id
        == str(event.event_id)
    )

    assert (
        result.notification_message_id
        == "sns-001"
    )

    publisher.publish.assert_called_once()

    store.complete.assert_called_once_with(
        claim
    )

    store.release.assert_not_called()


def test_completed_message_is_duplicate() -> None:
    store = Mock()
    publisher = Mock()

    message, event = (
        build_sqs_message()
    )

    store.claim.return_value = None

    store.get_status.return_value = (
        IdempotencyStatus.COMPLETED
    )

    service = build_service(
        store=store,
        publisher=publisher,
    )

    result = service.process_message(
        message
    )

    assert (
        result.status
        == AlertProcessingStatus.DUPLICATE
    )

    assert (
        result.event_id
        == str(event.event_id)
    )

    publisher.publish.assert_not_called()


def test_processing_message_returns_in_progress() -> None:
    store = Mock()
    publisher = Mock()

    message, _ = (
        build_sqs_message()
    )

    store.claim.return_value = None

    store.get_status.return_value = (
        IdempotencyStatus.PROCESSING
    )

    service = build_service(
        store=store,
        publisher=publisher,
    )

    result = service.process_message(
        message
    )

    assert (
        result.status
        == AlertProcessingStatus.IN_PROGRESS
    )

    publisher.publish.assert_not_called()


def test_missing_status_is_treated_as_in_progress() -> None:
    store = Mock()
    publisher = Mock()

    message, _ = (
        build_sqs_message()
    )

    store.claim.return_value = None
    store.get_status.return_value = None

    service = build_service(
        store=store,
        publisher=publisher,
    )

    result = service.process_message(
        message
    )

    assert (
        result.status
        == AlertProcessingStatus.IN_PROGRESS
    )

    publisher.publish.assert_not_called()


def test_sns_failure_releases_claim() -> None:
    store = Mock()
    publisher = Mock()

    message, event = (
        build_sqs_message()
    )

    claim = IdempotencyClaim(
        event_id=str(
            event.event_id
        ),
        claim_id="claim-001",
    )

    store.claim.return_value = claim

    publisher.publish.side_effect = (
        RuntimeError(
            "SNS unavailable"
        )
    )

    service = build_service(
        store=store,
        publisher=publisher,
    )

    with pytest.raises(
        RuntimeError,
        match="SNS unavailable",
    ):
        service.process_message(
            message
        )

    store.release.assert_called_once_with(
        claim
    )

    store.complete.assert_not_called()


def test_complete_failure_does_not_release_claim() -> None:
    store = Mock()
    publisher = Mock()

    message, event = (
        build_sqs_message()
    )

    claim = IdempotencyClaim(
        event_id=str(
            event.event_id
        ),
        claim_id="claim-001",
    )

    store.claim.return_value = claim

    publisher.publish.return_value = (
        SnsPublishResult(
            message_id="sns-001"
        )
    )

    store.complete.side_effect = (
        RuntimeError(
            "DynamoDB unavailable"
        )
    )

    service = build_service(
        store=store,
        publisher=publisher,
    )

    with pytest.raises(
        RuntimeError,
        match="DynamoDB unavailable",
    ):
        service.process_message(
            message
        )

    publisher.publish.assert_called_once()

    store.release.assert_not_called()


def test_invalid_message_stops_before_claim() -> None:
    store = Mock()
    publisher = Mock()

    service = build_service(
        store=store,
        publisher=publisher,
    )

    with pytest.raises(
        InvalidAlertMessageError,
    ):
        service.process_message(
            {
                "Body": "{broken"
            }
        )

    store.claim.assert_not_called()

    publisher.publish.assert_not_called()


# =========================================================
# Structured logging
# =========================================================


def test_successful_processing_emits_structured_logs(
    caplog,
) -> None:
    store = Mock()
    publisher = Mock()

    message, event = (
        build_sqs_message()
    )

    claim = IdempotencyClaim(
        event_id=str(
            event.event_id
        ),
        claim_id="claim-001",
    )

    store.claim.return_value = claim

    publisher.publish.return_value = (
        SnsPublishResult(
            message_id="sns-001"
        )
    )

    service = build_service(
        store=store,
        publisher=publisher,
    )

    with caplog.at_level(
        logging.INFO,
        logger=(
            "realstock."
            "alert_worker.service"
        ),
    ):
        service.process_message(
            message
        )

    messages = [
        record.getMessage()
        for record in caplog.records
    ]

    assert (
        "risk alert received"
        in messages
    )

    assert (
        "idempotency claim acquired"
        in messages
    )

    assert (
        "risk notification published"
        in messages
    )

    assert (
        "risk alert processing completed"
        in messages
    )

    received_record = next(
        record
        for record in caplog.records
        if (
            record.getMessage()
            == "risk alert received"
        )
    )

    fields = received_record.structured_fields

    assert (
        fields["severity"]
        == "CRITICAL"
    )

    assert (
        fields["risk_type"]
        == "PRICE_MOVE_PERCENT"
    )

    assert (
        fields["market"]
        == "US"
    )

    assert (
        fields["symbol"]
        == "AAPL"
    )


def test_duplicate_processing_is_logged(
    caplog,
) -> None:
    store = Mock()
    publisher = Mock()

    message, _ = (
        build_sqs_message()
    )

    store.claim.return_value = None

    store.get_status.return_value = (
        IdempotencyStatus.COMPLETED
    )

    service = build_service(
        store=store,
        publisher=publisher,
    )

    with caplog.at_level(
        logging.INFO,
        logger=(
            "realstock."
            "alert_worker.service"
        ),
    ):
        result = service.process_message(
            message
        )

    assert (
        result.status
        == AlertProcessingStatus.DUPLICATE
    )

    record = next(
        record
        for record in caplog.records
        if (
            record.getMessage()
            == (
                "duplicate risk alert "
                "suppressed"
            )
        )
    )

    fields = record.structured_fields

    assert (
        fields["idempotency_status"]
        == "COMPLETED"
    )


def test_sns_failure_is_logged(
    caplog,
) -> None:
    store = Mock()
    publisher = Mock()

    message, event = (
        build_sqs_message()
    )

    claim = IdempotencyClaim(
        event_id=str(
            event.event_id
        ),
        claim_id="claim-001",
    )

    store.claim.return_value = claim

    publisher.publish.side_effect = (
        RuntimeError(
            "SNS unavailable"
        )
    )

    service = build_service(
        store=store,
        publisher=publisher,
    )

    with caplog.at_level(
        logging.ERROR,
        logger=(
            "realstock."
            "alert_worker.service"
        ),
    ):
        with pytest.raises(
            RuntimeError,
            match="SNS unavailable",
        ):
            service.process_message(
                message
            )

    record = next(
        record
        for record in caplog.records
        if (
            record.getMessage()
            == (
                "notification publish failed; "
                "idempotency claim released"
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
        fields["claim_id"]
        == "claim-001"
    )

    store.release.assert_called_once_with(
        claim
    )


def test_completion_failure_is_logged_without_release(
    caplog,
) -> None:
    store = Mock()
    publisher = Mock()

    message, event = (
        build_sqs_message()
    )

    claim = IdempotencyClaim(
        event_id=str(
            event.event_id
        ),
        claim_id="claim-001",
    )

    store.claim.return_value = claim

    publisher.publish.return_value = (
        SnsPublishResult(
            message_id="sns-001"
        )
    )

    store.complete.side_effect = (
        RuntimeError(
            "DynamoDB unavailable"
        )
    )

    service = build_service(
        store=store,
        publisher=publisher,
    )

    with caplog.at_level(
        logging.ERROR,
        logger=(
            "realstock."
            "alert_worker.service"
        ),
    ):
        with pytest.raises(
            RuntimeError,
            match="DynamoDB unavailable",
        ):
            service.process_message(
                message
            )

    record = next(
        record
        for record in caplog.records
        if (
            record.getMessage()
            == (
                "idempotency completion failed "
                "after notification publish"
            )
        )
    )

    fields = record.structured_fields

    assert (
        fields["claim_id"]
        == "claim-001"
    )

    assert (
        fields[
            "notification_message_id"
        ]
        == "sns-001"
    )

    store.release.assert_not_called()


# =========================================================
# Metrics
# =========================================================


def test_success_metrics_are_recorded() -> None:
    store = Mock()
    publisher = Mock()

    message, event = (
        build_sqs_message()
    )

    claim = IdempotencyClaim(
        event_id=str(
            event.event_id
        ),
        claim_id="claim-001",
    )

    store.claim.return_value = claim

    publisher.publish.return_value = (
        SnsPublishResult(
            message_id="sns-001"
        )
    )

    sink = InMemoryMetricSink()

    service = build_service(
        store=store,
        publisher=publisher,
        metrics=MetricsRecorder(
            sink=sink
        ),
    )

    service.process_message(
        message
    )

    names = [
        metric.name
        for metric in sink.metrics
    ]

    assert (
        "AlertMessagesReceived"
        in names
    )

    assert (
        "AlertNotificationsPublished"
        in names
    )

    assert (
        "AlertProcessingCompleted"
        in names
    )

    assert (
        "AlertProcessingLatency"
        in names
    )

    assert (
        "AlertProcessingFailures"
        not in names
    )

    received = next(
        metric
        for metric in sink.metrics
        if (
            metric.name
            == "AlertMessagesReceived"
        )
    )

    assert (
        received.dimensions
        == {
            "Severity": "CRITICAL",
            "Market": "US",
        }
    )

    assert (
        received.unit
        == MetricUnit.COUNT
    )

    latency = next(
        metric
        for metric in sink.metrics
        if (
            metric.name
            == "AlertProcessingLatency"
        )
    )

    assert (
        latency.unit
        == MetricUnit.MILLISECONDS
    )

    assert latency.value >= 0


def test_duplicate_metric_is_recorded() -> None:
    store = Mock()
    publisher = Mock()

    message, _ = (
        build_sqs_message()
    )

    store.claim.return_value = None

    store.get_status.return_value = (
        IdempotencyStatus.COMPLETED
    )

    sink = InMemoryMetricSink()

    service = build_service(
        store=store,
        publisher=publisher,
        metrics=MetricsRecorder(
            sink=sink
        ),
    )

    result = service.process_message(
        message
    )

    assert (
        result.status
        == AlertProcessingStatus.DUPLICATE
    )

    names = [
        metric.name
        for metric in sink.metrics
    ]

    assert (
        "AlertMessagesReceived"
        in names
    )

    assert (
        "DuplicateAlertsSuppressed"
        in names
    )

    assert (
        "AlertProcessingLatency"
        in names
    )

    assert (
        "AlertNotificationsPublished"
        not in names
    )

    assert (
        "AlertProcessingCompleted"
        not in names
    )

    assert (
        "AlertProcessingFailures"
        not in names
    )


def test_sns_failure_metrics_are_recorded() -> None:
    store = Mock()
    publisher = Mock()

    message, event = (
        build_sqs_message()
    )

    claim = IdempotencyClaim(
        event_id=str(
            event.event_id
        ),
        claim_id="claim-001",
    )

    store.claim.return_value = claim

    publisher.publish.side_effect = (
        RuntimeError(
            "SNS unavailable"
        )
    )

    sink = InMemoryMetricSink()

    service = build_service(
        store=store,
        publisher=publisher,
        metrics=MetricsRecorder(
            sink=sink
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="SNS unavailable",
    ):
        service.process_message(
            message
        )

    names = [
        metric.name
        for metric in sink.metrics
    ]

    assert (
        "AlertMessagesReceived"
        in names
    )

    assert (
        "AlertProcessingFailures"
        in names
    )

    assert (
        "AlertProcessingLatency"
        in names
    )

    assert (
        "AlertNotificationsPublished"
        not in names
    )

    assert (
        "AlertProcessingCompleted"
        not in names
    )

    store.release.assert_called_once_with(
        claim
    )


def test_completion_failure_metrics_preserve_publish_fact() -> None:
    store = Mock()
    publisher = Mock()

    message, event = (
        build_sqs_message()
    )

    claim = IdempotencyClaim(
        event_id=str(
            event.event_id
        ),
        claim_id="claim-001",
    )

    store.claim.return_value = claim

    publisher.publish.return_value = (
        SnsPublishResult(
            message_id="sns-001"
        )
    )

    store.complete.side_effect = (
        RuntimeError(
            "DynamoDB unavailable"
        )
    )

    sink = InMemoryMetricSink()

    service = build_service(
        store=store,
        publisher=publisher,
        metrics=MetricsRecorder(
            sink=sink
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="DynamoDB unavailable",
    ):
        service.process_message(
            message
        )

    names = [
        metric.name
        for metric in sink.metrics
    ]

    assert (
        "AlertMessagesReceived"
        in names
    )

    assert (
        "AlertNotificationsPublished"
        in names
    )

    assert (
        "AlertProcessingFailures"
        in names
    )

    assert (
        "AlertProcessingLatency"
        in names
    )

    assert (
        "AlertProcessingCompleted"
        not in names
    )

    store.release.assert_not_called()