from __future__ import annotations

import time
from uuid import uuid4

import pytest

from libs.aws import get_dynamodb_client
from services.alert_worker import (
    DEFAULT_IDEMPOTENCY_TABLE_NAME,
    DynamoDbIdempotencyStore,
)

pytestmark = pytest.mark.integration


TABLE_NAME = (
    DEFAULT_IDEMPOTENCY_TABLE_NAME
)


def ensure_table() -> None:
    client = get_dynamodb_client()

    try:
        client.describe_table(
            TableName=TABLE_NAME,
        )
        return

    except (
        client.exceptions
        .ResourceNotFoundException
    ):
        pass

    client.create_table(
        TableName=TABLE_NAME,
        KeySchema=[
            {
                "AttributeName": "event_id",
                "KeyType": "HASH",
            }
        ],
        AttributeDefinitions=[
            {
                "AttributeName": "event_id",
                "AttributeType": "S",
            }
        ],
        BillingMode="PAY_PER_REQUEST",
    )

    client.get_waiter(
        "table_exists"
    ).wait(
        TableName=TABLE_NAME
    )

    client.update_time_to_live(
        TableName=TABLE_NAME,
        TimeToLiveSpecification={
            "Enabled": True,
            "AttributeName": "expires_at",
        },
    )


def test_dynamodb_idempotency_lifecycle() -> None:
    client = get_dynamodb_client()

    ensure_table()

    event_id = (
        f"alert-worker-{uuid4()}"
    )

    store = DynamoDbIdempotencyStore(
        table_name=TABLE_NAME,
        processing_lease_seconds=60,
        completed_retention_seconds=3600,
        client=client,
    )

    try:
        first_claim = store.claim(
            event_id=event_id
        )

        assert first_claim is not None

        duplicate_while_processing = (
            store.claim(
                event_id=event_id
            )
        )

        assert (
            duplicate_while_processing
            is None
        )

        store.complete(
            first_claim
        )

        item = client.get_item(
            TableName=TABLE_NAME,
            Key={
                "event_id": {
                    "S": event_id,
                }
            },
            ConsistentRead=True,
        )["Item"]

        assert (
            item["status"]["S"]
            == "COMPLETED"
        )

        assert (
            item["claim_id"]["S"]
            == first_claim.claim_id
        )

        assert (
            int(
                item["expires_at"]["N"]
            )
            > int(time.time())
        )

        duplicate_after_complete = (
            store.claim(
                event_id=event_id
            )
        )

        assert (
            duplicate_after_complete
            is None
        )

    finally:
        client.delete_item(
            TableName=TABLE_NAME,
            Key={
                "event_id": {
                    "S": event_id,
                }
            },
        )


def test_failed_processing_claim_can_be_released() -> None:
    client = get_dynamodb_client()

    ensure_table()

    event_id = (
        f"alert-worker-release-{uuid4()}"
    )

    store = DynamoDbIdempotencyStore(
        table_name=TABLE_NAME,
        client=client,
    )

    try:
        first_claim = store.claim(
            event_id=event_id
        )

        assert first_claim is not None

        store.release(
            first_claim
        )

        second_claim = store.claim(
            event_id=event_id
        )

        assert second_claim is not None

        assert (
            second_claim.claim_id
            != first_claim.claim_id
        )

    finally:
        client.delete_item(
            TableName=TABLE_NAME,
            Key={
                "event_id": {
                    "S": event_id,
                }
            },
        )