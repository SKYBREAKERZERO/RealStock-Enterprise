from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from services.alert_worker.idempotency import (
    IdempotencyStatus,
    IdempotencyStore,
)
from services.alert_worker.notification import (
    SnsRiskNotificationPublisher,
)
from services.alert_worker.parser import (
    AlertMessageParser,
)


class AlertProcessingStatus(StrEnum):
    PUBLISHED = "PUBLISHED"
    DUPLICATE = "DUPLICATE"
    IN_PROGRESS = "IN_PROGRESS"


@dataclass(frozen=True)
class AlertProcessingResult:
    status: AlertProcessingStatus
    event_id: str
    notification_message_id: (
        str | None
    ) = None


class AlertWorkerService:
    """
    Application service for one SQS risk-alert message.

    It deliberately does not delete SQS messages.
    A transport-level consumer will decide ACK semantics
    based on AlertProcessingStatus.
    """

    def __init__(
        self,
        *,
        parser: AlertMessageParser,
        idempotency_store: IdempotencyStore,
        notification_publisher: (
            SnsRiskNotificationPublisher
        ),
    ) -> None:
        self._parser = parser
        self._idempotency_store = (
            idempotency_store
        )
        self._notification_publisher = (
            notification_publisher
        )

    def process_message(
        self,
        message: dict[str, Any],
    ) -> AlertProcessingResult:
        parsed = self._parser.parse(
            message
        )

        event = parsed.detail

        event_id = str(
            event.event_id
        )

        claim = (
            self._idempotency_store.claim(
                event_id=event_id
            )
        )

        if claim is None:
            status = (
                self._idempotency_store
                .get_status(
                    event_id=event_id
                )
            )

            if (
                status
                == IdempotencyStatus.COMPLETED
            ):
                return AlertProcessingResult(
                    status=(
                        AlertProcessingStatus
                        .DUPLICATE
                    ),
                    event_id=event_id,
                )

            return AlertProcessingResult(
                status=(
                    AlertProcessingStatus
                    .IN_PROGRESS
                ),
                event_id=event_id,
            )

        try:
            publish_result = (
                self._notification_publisher
                .publish(
                    event
                )
            )

        except Exception:
            self._idempotency_store.release(
                claim
            )

            raise

        try:
            self._idempotency_store.complete(
                claim
            )

        except Exception:
            # SNS has already succeeded.
            #
            # Do not release the claim here because an
            # immediate SQS retry would almost certainly
            # produce a duplicate notification.
            #
            # The processing lease remains as a temporary
            # duplicate-suppression barrier.
            raise

        return AlertProcessingResult(
            status=(
                AlertProcessingStatus.PUBLISHED
            ),
            event_id=event_id,
            notification_message_id=(
                publish_result.message_id
            ),
        )