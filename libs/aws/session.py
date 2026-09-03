from __future__ import annotations

from functools import lru_cache

import boto3
from boto3.session import Session

from libs.config import get_settings


LOCALSTACK_ACCESS_KEY = "test"
LOCALSTACK_SECRET_KEY = "test"


@lru_cache(maxsize=1)
def get_aws_session() -> Session:
    """
    Create one cached boto3 Session per Python process.

    Local environment:
        - Uses LocalStack-only fake AWS credentials.
        - Uses the configured AWS region.

    AWS environments:
        - Does not provide static credentials.
        - Uses the standard AWS credential provider chain:
        IAM role, ECS task role, AWS SSO, STS, etc.
    """

    settings = get_settings()

    if settings.use_localstack:
        return boto3.Session(
            aws_access_key_id=LOCALSTACK_ACCESS_KEY,
            aws_secret_access_key=LOCALSTACK_SECRET_KEY,
            region_name=settings.aws_region,
        )

    return boto3.Session(
        region_name=settings.aws_region,
    )