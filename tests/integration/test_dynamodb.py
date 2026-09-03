import time
import uuid

import pytest
from botocore.exceptions import ClientError

from libs.aws import get_dynamodb_client


pytestmark = pytest.mark.integration

TABLE_NAME = "realstock-idempotency-local"


def ensure_table() -> None:
    client = get_dynamodb_client()

    try:
        client.describe_table(
            TableName=TABLE_NAME,
        )
        return

    except client.exceptions.ResourceNotFoundException:
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

    waiter = client.get_waiter(
        "table_exists"
    )

    waiter.wait(
        TableName=TABLE_NAME,
    )

    client.update_time_to_live(
        TableName=TABLE_NAME,
        TimeToLiveSpecification={
            "Enabled": True,
            "AttributeName": "expires_at",
        },
    )


def test_dynamodb_conditional_write_prevents_duplicate() -> None:
    client = get_dynamodb_client()

    ensure_table()

    event_id = (
        f"pytest-{uuid.uuid4()}"
    )

    now = int(time.time())

    item = {
        "event_id": {
            "S": event_id,
        },
        "status": {
            "S": "PROCESSING",
        },
        "created_at": {
            "N": str(now),
        },
        "expires_at": {
            "N": str(now + 3600),
        },
    }

    try:
        first_response = client.put_item(
            TableName=TABLE_NAME,
            Item=item,
            ConditionExpression=(
                "attribute_not_exists(event_id)"
            ),
        )

        assert (
            first_response["ResponseMetadata"]["HTTPStatusCode"]
            == 200
        )

        with pytest.raises(
            ClientError
        ) as error:
            client.put_item(
                TableName=TABLE_NAME,
                Item=item,
                ConditionExpression=(
                    "attribute_not_exists(event_id)"
                ),
            )

        error_code = (
            error.value.response["Error"]["Code"]
        )

        assert (
            error_code
            == "ConditionalCheckFailedException"
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