from __future__ import annotations

from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError

from services.alert_worker import (
    DynamoDbIdempotencyStore,
    IdempotencyClaim,
)

pytestmark = pytest.mark.unit


TABLE_NAME = (
    "realstock-idempotency-test"
)


def conditional_failure() -> ClientError:
    return ClientError(
        {
            "Error": {
                "Code":
                    "ConditionalCheckFailedException",
                "Message":
                    "conditional request failed",
            }
        },
        "PutItem",
    )


def test_claim_creates_processing_record() -> None:
    client = Mock()

    store = DynamoDbIdempotencyStore(
        table_name=TABLE_NAME,
        client=client,
    )

    claim = store.claim(
        event_id="risk-event-001"
    )

    assert claim is not None

    assert (
        claim.event_id
        == "risk-event-001"
    )

    assert claim.claim_id

    client.put_item.assert_called_once()

    request = (
        client.put_item.call_args.kwargs
    )

    assert (
        request["TableName"]
        == TABLE_NAME
    )

    assert (
        request["Item"]["status"]["S"]
        == "PROCESSING"
    )

    assert (
        request["Item"]["event_id"]["S"]
        == "risk-event-001"
    )

    assert (
        request["Item"]["claim_id"]["S"]
        == claim.claim_id
    )


def test_duplicate_claim_returns_none() -> None:
    client = Mock()

    client.put_item.side_effect = (
        conditional_failure()
    )

    store = DynamoDbIdempotencyStore(
        table_name=TABLE_NAME,
        client=client,
    )

    result = store.claim(
        event_id="risk-event-001"
    )

    assert result is None


def test_non_conditional_claim_error_propagates() -> None:
    client = Mock()

    client.put_item.side_effect = (
        ClientError(
            {
                "Error": {
                    "Code":
                        "ProvisionedThroughputExceededException",
                    "Message":
                        "throttled",
                }
            },
            "PutItem",
        )
    )

    store = DynamoDbIdempotencyStore(
        table_name=TABLE_NAME,
        client=client,
    )

    with pytest.raises(
        ClientError
    ):
        store.claim(
            event_id="risk-event-001"
        )


def test_complete_marks_claim_completed() -> None:
    client = Mock()

    store = DynamoDbIdempotencyStore(
        table_name=TABLE_NAME,
        client=client,
    )

    claim = IdempotencyClaim(
        event_id="risk-event-001",
        claim_id="claim-001",
    )

    store.complete(
        claim
    )

    client.update_item.assert_called_once()

    request = (
        client.update_item.call_args.kwargs
    )

    assert (
        request["Key"]["event_id"]["S"]
        == "risk-event-001"
    )

    assert (
        request[
            "ExpressionAttributeValues"
        ][":completed"]["S"]
        == "COMPLETED"
    )

    assert (
        request[
            "ExpressionAttributeValues"
        ][":claim_id"]["S"]
        == "claim-001"
    )


def test_release_deletes_owned_processing_claim() -> None:
    client = Mock()

    store = DynamoDbIdempotencyStore(
        table_name=TABLE_NAME,
        client=client,
    )

    claim = IdempotencyClaim(
        event_id="risk-event-001",
        claim_id="claim-001",
    )

    store.release(
        claim
    )

    client.delete_item.assert_called_once()

    request = (
        client.delete_item.call_args.kwargs
    )

    assert (
        request["Key"]["event_id"]["S"]
        == "risk-event-001"
    )

    assert (
        request[
            "ExpressionAttributeValues"
        ][":claim_id"]["S"]
        == "claim-001"
    )


def test_release_ignores_lost_ownership() -> None:
    client = Mock()

    client.delete_item.side_effect = (
        conditional_failure()
    )

    store = DynamoDbIdempotencyStore(
        table_name=TABLE_NAME,
        client=client,
    )

    store.release(
        IdempotencyClaim(
            event_id="risk-event-001",
            claim_id="old-claim",
        )
    )


def test_rejects_empty_event_id() -> None:
    store = DynamoDbIdempotencyStore(
        table_name=TABLE_NAME,
        client=Mock(),
    )

    with pytest.raises(
        ValueError,
        match="event_id",
    ):
        store.claim(
            event_id="   "
        )


def test_rejects_invalid_configuration() -> None:
    with pytest.raises(
        ValueError,
        match="table_name",
    ):
        DynamoDbIdempotencyStore(
            table_name=" ",
            client=Mock(),
        )

    with pytest.raises(
        ValueError,
        match="processing_lease_seconds",
    ):
        DynamoDbIdempotencyStore(
            table_name=TABLE_NAME,
            processing_lease_seconds=0,
            client=Mock(),
        )

    with pytest.raises(
        ValueError,
        match="completed_retention_seconds",
    ):
        DynamoDbIdempotencyStore(
            table_name=TABLE_NAME,
            completed_retention_seconds=0,
            client=Mock(),
        )

def test_get_status_returns_processing() -> None:
    client = Mock()

    client.get_item.return_value = {
        "Item": {
            "event_id": {
                "S": "risk-event-001",
            },
            "status": {
                "S": "PROCESSING",
            },
        }
    }

    store = DynamoDbIdempotencyStore(
        table_name=TABLE_NAME,
        client=client,
    )

    status = store.get_status(
        event_id="risk-event-001"
    )

    assert status is not None

    assert (
        status.value
        == "PROCESSING"
    )


def test_get_status_returns_completed() -> None:
    client = Mock()

    client.get_item.return_value = {
        "Item": {
            "event_id": {
                "S": "risk-event-001",
            },
            "status": {
                "S": "COMPLETED",
            },
        }
    }

    store = DynamoDbIdempotencyStore(
        table_name=TABLE_NAME,
        client=client,
    )

    status = store.get_status(
        event_id="risk-event-001"
    )

    assert status is not None

    assert (
        status.value
        == "COMPLETED"
    )


def test_get_status_returns_none_when_missing() -> None:
    client = Mock()

    client.get_item.return_value = {}

    store = DynamoDbIdempotencyStore(
        table_name=TABLE_NAME,
        client=client,
    )

    status = store.get_status(
        event_id="risk-event-001"
    )

    assert status is None