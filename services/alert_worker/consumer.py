from __future__ import annotations

import logging

from botocore.client import BaseClient

from libs.aws import get_sqs_client
from libs.observability import (
    MetricsRecorder,
    get_logger,
    log_event,
)
from services.alert_worker.service import (
    AlertProcessingResult,
    AlertProcessingStatus,
    AlertWorkerService,
)

LOGGER = get_logger(
    "realstock.alert_worker.consumer"
)


class SqsAlertConsumer:
    """
    Transport adapter for the Alert Worker.

    PUBLISHED / DUPLICATE:
        ACK by deleting the SQS message.

    IN_PROGRESS:
        Do not ACK.

    Exception:
        Do not ACK so SQS can retry.

    Observability:
        structured transport logs
        SQS receive counters
        ACK / NO-ACK counters
        processing failure counters
    """

    def __init__(
        self,
        *,
        queue_url: str,
        worker_service: AlertWorkerService,
        wait_time_seconds: int = 1,
        client: BaseClient | None = None,
        metrics: MetricsRecorder | None = None,
    ) -> None:
        normalized_queue_url = (
            queue_url.strip()
        )

        if not normalized_queue_url:
            raise ValueError(
                "queue_url must not be empty"
            )

        if not (
            0
            <= wait_time_seconds
            <= 20
        ):
            raise ValueError(
                "wait_time_seconds must be "
                "between 0 and 20"
            )

        self._queue_url = (
            normalized_queue_url
        )

        self._worker_service = (
            worker_service
        )

        self._wait_time_seconds = (
            wait_time_seconds
        )

        self._client = (
            client
            if client is not None
            else get_sqs_client()
        )

        self._metrics = (
            metrics
            if metrics is not None
            else MetricsRecorder()
        )

    @property
    def queue_url(self) -> str:
        return self._queue_url

    def poll_once(
        self,
    ) -> AlertProcessingResult | None:
        response = (
            self._client.receive_message(
                QueueUrl=self._queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=(
                    self._wait_time_seconds
                ),
            )
        )

        messages = response.get(
            "Messages",
            [],
        )

        if not messages:
            return None

        message = messages[0]

        message_id = message.get(
            "MessageId"
        )

        receipt_handle = message.get(
            "ReceiptHandle"
        )

        self._metrics.increment(
            "SqsMessagesReceived"
        )

        log_event(
            LOGGER,
            logging.INFO,
            "sqs alert message received",
            sqs_message_id=message_id,
        )

        if not isinstance(
            receipt_handle,
            str,
        ):
            self._metrics.increment(
                "SqsMessagesNotAcknowledged",
                dimensions={
                    "Reason": (
                        "MISSING_RECEIPT_HANDLE"
                    )
                },
            )

            self._metrics.increment(
                "SqsProcessingFailures",
                dimensions={
                    "FailureStage": "VALIDATION"
                },
            )

            log_event(
                LOGGER,
                logging.ERROR,
                (
                    "sqs alert message missing "
                    "receipt handle"
                ),
                sqs_message_id=message_id,
            )

            raise RuntimeError(
                "SQS message does not contain "
                "ReceiptHandle"
            )

        try:
            result = (
                self._worker_service
                .process_message(
                    message
                )
            )

        except Exception:
            self._metrics.increment(
                "SqsMessagesNotAcknowledged",
                dimensions={
                    "Reason": (
                        "PROCESSING_FAILURE"
                    )
                },
            )

            self._metrics.increment(
                "SqsProcessingFailures",
                dimensions={
                    "FailureStage": "WORKER"
                },
            )

            LOGGER.exception(
                (
                    "alert message processing "
                    "failed; message not "
                    "acknowledged"
                ),
                extra={
                    "structured_fields": {
                        "sqs_message_id": (
                            message_id
                        ),
                    }
                },
            )

            raise

        if result.status in {
            AlertProcessingStatus.PUBLISHED,
            AlertProcessingStatus.DUPLICATE,
        }:
            try:
                self._client.delete_message(
                    QueueUrl=self._queue_url,
                    ReceiptHandle=(
                        receipt_handle
                    ),
                )

            except Exception:
                self._metrics.increment(
                    "SqsMessagesNotAcknowledged",
                    dimensions={
                        "Reason": (
                            "ACK_FAILURE"
                        )
                    },
                )

                self._metrics.increment(
                    "SqsProcessingFailures",
                    dimensions={
                        "FailureStage": "ACK"
                    },
                )

                LOGGER.exception(
                    (
                        "sqs alert message "
                        "acknowledgement failed"
                    ),
                    extra={
                        "structured_fields": {
                            "sqs_message_id": (
                                message_id
                            ),
                            "event_id": (
                                result.event_id
                            ),
                            (
                                "processing_status"
                            ): (
                                result.status.value
                            ),
                        }
                    },
                )

                raise

            self._metrics.increment(
                "SqsMessagesAcknowledged",
                dimensions={
                    "ProcessingStatus": (
                        result.status.value
                    )
                },
            )

            log_event(
                LOGGER,
                logging.INFO,
                "sqs alert message acknowledged",
                sqs_message_id=message_id,
                event_id=result.event_id,
                processing_status=(
                    result.status.value
                ),
                acknowledged=True,
            )

        else:
            self._metrics.increment(
                "SqsMessagesNotAcknowledged",
                dimensions={
                    "Reason": "IN_PROGRESS"
                },
            )

            log_event(
                LOGGER,
                logging.INFO,
                (
                    "sqs alert message left "
                    "unacknowledged"
                ),
                sqs_message_id=message_id,
                event_id=result.event_id,
                processing_status=(
                    result.status.value
                ),
                acknowledged=False,
            )

        return result