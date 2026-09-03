from __future__ import annotations

from functools import lru_cache
from typing import Any

from botocore.client import BaseClient
from botocore.config import Config

from libs.aws.session import get_aws_session
from libs.config import get_settings


AWS_CLIENT_CONFIG = Config(
    retries={
        "max_attempts": 3,
        "mode": "standard",
    },
    connect_timeout=5,
    read_timeout=10,
)


def _create_client(service_name: str) -> BaseClient:
    """
    Create an AWS service client.

    Local:
        boto3 -> LocalStack

    dev/staging/prod:
        boto3 -> real AWS

    Business code must not hard-code endpoint URLs.
    """

    settings = get_settings()
    session = get_aws_session()

    kwargs: dict[str, Any] = {
        "service_name": service_name,
        "region_name": settings.aws_region,
        "config": AWS_CLIENT_CONFIG,
    }

    if settings.use_localstack:
        kwargs["endpoint_url"] = settings.aws_endpoint_url

    return session.client(**kwargs)


@lru_cache(maxsize=1)
def get_sts_client() -> BaseClient:
    return _create_client("sts")


@lru_cache(maxsize=1)
def get_s3_client() -> BaseClient:
    return _create_client("s3")


@lru_cache(maxsize=1)
def get_dynamodb_client() -> BaseClient:
    return _create_client("dynamodb")


@lru_cache(maxsize=1)
def get_kinesis_client() -> BaseClient:
    return _create_client("kinesis")


@lru_cache(maxsize=1)
def get_eventbridge_client() -> BaseClient:
    return _create_client("events")


@lru_cache(maxsize=1)
def get_sqs_client() -> BaseClient:
    return _create_client("sqs")


@lru_cache(maxsize=1)
def get_sns_client() -> BaseClient:
    return _create_client("sns")


@lru_cache(maxsize=1)
def get_secretsmanager_client() -> BaseClient:
    return _create_client("secretsmanager")


@lru_cache(maxsize=1)
def get_kms_client() -> BaseClient:
    return _create_client("kms")