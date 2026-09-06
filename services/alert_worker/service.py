from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from libs.observability import (
    MetricsRecorder,
    bind_observability_context,
    get_logger,
    log_event,
)
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

LOGGER = get_logger(
    "realstock.alert_worker.service"
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

    SQS ACK semantics remain outside this class.
    """

    def __init__(
        self,
        *,
        parser: AlertMessageParser,
        idempotency_store: IdempotencyStore,
        notification_publisher: (
            SnsRiskNotificationPublisher
        ),
        metrics: MetricsRecorder | None = None,
    ) -> None:
        self._parser = parser

        self._idempotency_store = (
            idempotency_store
        )

        self._notification_publisher = (
            notification_publisher
        )

        self._metrics = (
            metrics
            if metrics is not None
            else MetricsRecorder()
        )

    def process_message(
        self,
        message: dict[str, Any],
    ) -> AlertProcessingResult:
        with self._metrics.timer(
            "AlertProcessingLatency"
        ):
            try:
                return (
                    self._process_message(
                        message
                    )
                )

            except Exception:
                self._metrics.increment(
                    "AlertProcessingFailures"
                )

                raise

    def _process_message(
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

        correlation_id = str(
            event.correlation_id
        )

        causation_id = (
            str(
                event.causation_id
            )
            if event.causation_id
            is not None
            else None
        )

        severity = str(
            event.payload.get(
                "severity",
                "UNKNOWN",
            )
        )

        market = str(
            event.payload.get(
                "market",
                "UNKNOWN",
            )
        )

        self._metrics.increment(
            "AlertMessagesReceived",
            dimensions={
                "Severity": severity,
                "Market": market,
            },
        )

        with bind_observability_context(
            correlation_id=correlation_id,
            event_id=event_id,
            causation_id=causation_id,
        ):
            log_event(
                LOGGER,
                logging.INFO,
                "risk alert received",
                risk_type=(
                    event.payload.get(
                        "risk_type"
                    )
                ),
                severity=severity,
                market=market,
                symbol=(
                    event.payload.get(
                        "symbol"
                    )
                ),
            )

            claim = (
                self._idempotency_store
                .claim(
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
                    self._metrics.increment(
                        "DuplicateAlertsSuppressed"
                    )

                    log_event(
                        LOGGER,
                        logging.INFO,
                        (
                            "duplicate risk alert "
                            "suppressed"
                        ),
                        idempotency_status=(
                            IdempotencyStatus
                            .COMPLETED
                            .value
                        ),
                    )

                    return (
                        AlertProcessingResult(
                            status=(
                                AlertProcessingStatus
                                .DUPLICATE
                            ),
                            event_id=event_id,
                        )
                    )

                self._metrics.increment(
                    "AlertsInProgress"
                )

                log_event(
                    LOGGER,
                    logging.INFO,
                    (
                        "risk alert already "
                        "in progress"
                    ),
                    idempotency_status=(
                        status.value
                        if status is not None
                        else None
                    ),
                )

                return (
                    AlertProcessingResult(
                        status=(
                            AlertProcessingStatus
                            .IN_PROGRESS
                        ),
                        event_id=event_id,
                    )
                )

            log_event(
                LOGGER,
                logging.INFO,
                "idempotency claim acquired",
                claim_id=claim.claim_id,
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

                LOGGER.exception(
                    (
                        "notification publish failed; "
                        "idempotency claim released"
                    ),
                    extra={
                        "structured_fields": {
                            "claim_id": (
                                claim.claim_id
                            ),
                        }
                    },
                )

                raise

            self._metrics.increment(
                "AlertNotificationsPublished",
                dimensions={
                    "Severity": severity,
                    "Market": market,
                },
            )

            log_event(
                LOGGER,
                logging.INFO,
                "risk notification published",
                notification_message_id=(
                    publish_result.message_id
                ),
            )

            try:
                self._idempotency_store.complete(
                    claim
                )

            except Exception:
                LOGGER.exception(
                    (
                        "idempotency completion failed "
                        "after notification publish"
                    ),
                    extra={
                        "structured_fields": {
                            "claim_id": (
                                claim.claim_id
                            ),
                            (
                                "notification_"
                                "message_id"
                            ): (
                                publish_result
                                .message_id
                            ),
                        }
                    },
                )

                raise

            self._metrics.increment(
                "AlertProcessingCompleted"
            )

            log_event(
                LOGGER,
                logging.INFO,
                "risk alert processing completed",
                idempotency_status=(
                    IdempotencyStatus
                    .COMPLETED
                    .value
                ),
                notification_message_id=(
                    publish_result.message_id
                ),
            )

            return (
                AlertProcessingResult(
                    status=(
                        AlertProcessingStatus
                        .PUBLISHED
                    ),
                    event_id=event_id,
                    notification_message_id=(
                        publish_result.message_id
                    ),
                )
            )