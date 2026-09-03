import uuid

import pytest
from botocore.exceptions import ClientError

from libs.aws import get_s3_client
from libs.config import get_settings


pytestmark = pytest.mark.integration

TEST_BUCKET = "realstock-market-data-local"


def ensure_bucket() -> None:
    settings = get_settings()
    client = get_s3_client()

    try:
        client.head_bucket(
            Bucket=TEST_BUCKET,
        )
        return

    except ClientError:
        pass

    if settings.aws_region == "us-east-1":
        client.create_bucket(
            Bucket=TEST_BUCKET,
        )
    else:
        client.create_bucket(
            Bucket=TEST_BUCKET,
            CreateBucketConfiguration={
                "LocationConstraint": settings.aws_region,
            },
        )


def test_s3_put_get_delete_object() -> None:
    client = get_s3_client()

    ensure_bucket()

    key = (
        "pytest/"
        f"{uuid.uuid4()}.txt"
    )

    body = b"RealStock pytest S3 PASS"

    try:
        put_response = client.put_object(
            Bucket=TEST_BUCKET,
            Key=key,
            Body=body,
        )

        assert (
            put_response["ResponseMetadata"]["HTTPStatusCode"]
            == 200
        )

        get_response = client.get_object(
            Bucket=TEST_BUCKET,
            Key=key,
        )

        stored_body = (
            get_response["Body"].read()
        )

        assert stored_body == body

    finally:
        client.delete_object(
            Bucket=TEST_BUCKET,
            Key=key,
        )