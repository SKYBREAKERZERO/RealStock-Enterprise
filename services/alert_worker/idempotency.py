from __future__ import annotations

import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import uuid4

from botocore.client import BaseClient
from botocore.exceptions import ClientError

from libs.aws import get_dynamodb_client

DEFAULT_IDEMPOTENCY_TABLE_NAME = (
    "realstock-idempotency-local"
)

DEFAULT_PROCESSING_LEASE_SECONDS = 60

DEFAULT_COMPLETED_RETENTION_SECONDS = (
    24 * 60 * 60
)


class IdempotencyStatus(StrEnum):
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"


@dataclass(frozen=True)
class IdempotencyClaim:
    event_id: str
    claim_id: str


class IdempotencyStore(Protocol):
    def claim(
        self,
        *,
        event_id: str,
    ) -> IdempotencyClaim | None:
        ...

    def get_status(
        self,
        *,
        event_id: str,
    ) -> IdempotencyStatus | None:
        ...

    def complete(
        self,
        claim: IdempotencyClaim,
    ) -> None:
        ...

    def release(
        self,
        claim: IdempotencyClaim,
    ) -> None:
        ...


class DynamoDbIdempotencyStore:
    """
    DynamoDB-backed idempotency store.

    PROCESSING records use a short lease.
    COMPLETED records use a longer retention TTL.
    """

    def __init__(
        self,
        *,
        table_name: str = (
            DEFAULT_IDEMPOTENCY_TABLE_NAME
        ),
        processing_lease_seconds: int = (
            DEFAULT_PROCESSING_LEASE_SECONDS
        ),
        completed_retention_seconds: int = (
            DEFAULT_COMPLETED_RETENTION_SECONDS
        ),
        client: BaseClient | None = None,
    ) -> None:
        normalized_table_name = (
            table_name.strip()
        )

        if not normalized_table_name:
            raise ValueError(
                "table_name must not be empty"
            )

        if processing_lease_seconds <= 0:
            raise ValueError(
                "processing_lease_seconds must be "
                "greater than zero"
            )

        if completed_retention_seconds <= 0:
            raise ValueError(
                "completed_retention_seconds must be "
                "greater than zero"
            )

        self._table_name = (
            normalized_table_name
        )

        self._processing_lease_seconds = (
            processing_lease_seconds
        )

        self._completed_retention_seconds = (
            completed_retention_seconds
        )

        self._client = (
            client
            if client is not None
            else get_dynamodb_client()
        )

    @property
    def table_name(
        self,
    ) -> str:
        return self._table_name

    def claim(
        self,
        *,
        event_id: str,
    ) -> IdempotencyClaim | None:
        normalized_event_id = (
            event_id.strip()
        )

        if not normalized_event_id:
            raise ValueError(
                "event_id must not be empty"
            )

        now = int(time.time())

        claim_id = str(
            uuid4()
        )

        lease_expires_at = (
            now
            + self._processing_lease_seconds
        )

        try:
            self._client.put_item(
                TableName=self._table_name,
                Item={
                    "event_id": {
                        "S":
                            normalized_event_id,
                    },
                    "status": {
                        "S":
                            IdempotencyStatus.PROCESSING.value,
                    },
                    "claim_id": {
                        "S": claim_id,
                    },
                    "created_at": {
                        "N": str(now),
                    },
                    "updated_at": {
                        "N": str(now),
                    },
                    "expires_at": {
                        "N": str(
                            lease_expires_at
                        ),
                    },
                },
                ConditionExpression=(
                    "attribute_not_exists(event_id) "
                    "OR expires_at < :now"
                ),
                ExpressionAttributeValues={
                    ":now": {
                        "N": str(now),
                    }
                },
            )

        except ClientError as exc:
            error_code = (
                exc.response[
                    "Error"
                ]["Code"]
            )

            if (
                error_code
                == "ConditionalCheckFailedException"
            ):
                return None

            raise

        return IdempotencyClaim(
            event_id=normalized_event_id,
            claim_id=claim_id,
        )

    def get_status(
        self,
        *,
        event_id: str,
    ) -> IdempotencyStatus | None:
        normalized_event_id = (
            event_id.strip()
        )

        if not normalized_event_id:
            raise ValueError(
                "event_id must not be empty"
            )

        response = self._client.get_item(
            TableName=self._table_name,
            Key={
                "event_id": {
                    "S":
                        normalized_event_id,
                }
            },
            ConsistentRead=True,
        )

        item = response.get(
            "Item"
        )

        if not item:
            return None

        status_value = (
            item.get(
                "status",
                {},
            ).get("S")
        )

        if not status_value:
            raise RuntimeError(
                "idempotency record does not "
                "contain status"
            )

        try:
            return IdempotencyStatus(
                status_value
            )

        except ValueError as exc:
            raise RuntimeError(
                "unknown idempotency status: "
                f"{status_value}"
            ) from exc

    def complete(
        self,
        claim: IdempotencyClaim,
    ) -> None:
        now = int(time.time())

        expires_at = (
            now
            + self._completed_retention_seconds
        )

        self._client.update_item(
            TableName=self._table_name,
            Key={
                "event_id": {
                    "S": claim.event_id,
                }
            },
            UpdateExpression=(
                "SET #status = :completed, "
                "updated_at = :now, "
                "expires_at = :expires_at"
            ),
            ConditionExpression=(
                "claim_id = :claim_id "
                "AND #status = :processing"
            ),
            ExpressionAttributeNames={
                "#status": "status",
            },
            ExpressionAttributeValues={
                ":completed": {
                    "S":
                        IdempotencyStatus.COMPLETED.value,
                },
                ":processing": {
                    "S":
                        IdempotencyStatus.PROCESSING.value,
                },
                ":claim_id": {
                    "S":
                        claim.claim_id,
                },
                ":now": {
                    "N": str(now),
                },
                ":expires_at": {
                    "N":
                        str(expires_at),
                },
            },
        )

    def release(
        self,
        claim: IdempotencyClaim,
    ) -> None:
        try:
            self._client.delete_item(
                TableName=self._table_name,
                Key={
                    "event_id": {
                        "S":
                            claim.event_id,
                    }
                },
                ConditionExpression=(
                    "claim_id = :claim_id "
                    "AND #status = :processing"
                ),
                ExpressionAttributeNames={
                    "#status": "status",
                },
                ExpressionAttributeValues={
                    ":claim_id": {
                        "S":
                            claim.claim_id,
                    },
                    ":processing": {
                        "S":
                            IdempotencyStatus.PROCESSING.value,
                    },
                },
            )

        except ClientError as exc:
            error_code = (
                exc.response[
                    "Error"
                ]["Code"]
            )

            if (
                error_code
                == "ConditionalCheckFailedException"
            ):
                return

            raise