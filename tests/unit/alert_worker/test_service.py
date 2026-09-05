from __future__ import annotations

import json
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
        "detail-type":
            "risk.alert.detected",
        "source":
            EVENTBRIDGE_RISK_SOURCE,
        "account":
            "000000000000",
        "time":
            "2026-09-05T14:00:00Z",
        "region":
            "ap-northeast-1",
        "resources": [],
        "detail":
            event.to_event_dict(),
    }

    message = {
        "MessageId": "sqs-001",
        "ReceiptHandle":
            "receipt-001",
        "Body":
            json.dumps(body),
    }

    return message, event


def build_service(
    *,
    store,
    publisher,
):
    return AlertWorkerService(
        parser=AlertMessageParser(),
        idempotency_store=store,
        notification_publisher=publisher,
    )


def test_process_message_publishes_and_completes() -> None:
    store = Mock()

    publisher = Mock()

    message, event = (
        build_sqs_message()
    )

    claim = IdempotencyClaim(
        event_id=str(event.event_id),
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
        event_id=str(event.event_id),
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
        event_id=str(event.event_id),
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