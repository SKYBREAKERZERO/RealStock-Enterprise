from __future__ import annotations

from botocore.client import BaseClient

from libs.aws import get_sqs_client
from services.alert_worker.service import (
    AlertProcessingResult,
    AlertProcessingStatus,
    AlertWorkerService,
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
    """

    def __init__(
        self,
        *,
        queue_url: str,
        worker_service: AlertWorkerService,
        wait_time_seconds: int = 1,
        client: BaseClient | None = None,
    ) -> None:
        normalized_queue_url = queue_url.strip()

        if not normalized_queue_url:
            raise ValueError(
                "queue_url must not be empty"
            )

        if not 0 <= wait_time_seconds <= 20:
            raise ValueError(
                "wait_time_seconds must be "
                "between 0 and 20"
            )

        self._queue_url = normalized_queue_url
        self._worker_service = worker_service
        self._wait_time_seconds = (
            wait_time_seconds
        )

        self._client = (
            client
            if client is not None
            else get_sqs_client()
        )

    @property
    def queue_url(self) -> str:
        return self._queue_url

    def poll_once(
        self,
    ) -> AlertProcessingResult | None:
        response = self._client.receive_message(
            QueueUrl=self._queue_url,
            MaxNumberOfMessages=1,
            WaitTimeSeconds=(
                self._wait_time_seconds
            ),
        )

        messages = response.get(
            "Messages",
            [],
        )

        if not messages:
            return None

        message = messages[0]

        receipt_handle = message.get(
            "ReceiptHandle"
        )

        if not isinstance(
            receipt_handle,
            str,
        ):
            raise RuntimeError(
                "SQS message does not contain "
                "ReceiptHandle"
            )

        result = (
            self._worker_service
            .process_message(
                message
            )
        )

        if result.status in {
            AlertProcessingStatus.PUBLISHED,
            AlertProcessingStatus.DUPLICATE,
        }:
            self._client.delete_message(
                QueueUrl=self._queue_url,
                ReceiptHandle=receipt_handle,
            )

        return result