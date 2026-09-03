from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from libs.aws import (
    get_dynamodb_client,
    get_s3_client,
    get_sts_client,
)
from libs.cache import get_redis_client
from libs.database import get_engine


router = APIRouter(
    tags=["health"],
)


@router.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
    }


@router.get("/health/ready")
def readiness() -> dict[str, object]:
    dependencies: dict[str, str] = {
        "postgresql": "unknown",
        "redis": "unknown",
        "localstack": "unknown",
        "s3": "unknown",
        "dynamodb": "unknown",
    }

    # ----------------------------------------------------------
    # PostgreSQL
    # ----------------------------------------------------------
    try:
        engine = get_engine()

        with engine.connect() as connection:
            result = connection.execute(
                text("SELECT 1")
            ).scalar_one()

        dependencies["postgresql"] = (
            "ok"
            if result == 1
            else "error"
        )

    except Exception:
        dependencies["postgresql"] = "error"

    # ----------------------------------------------------------
    # Redis
    # ----------------------------------------------------------
    try:
        redis_client = get_redis_client()

        dependencies["redis"] = (
            "ok"
            if redis_client.ping()
            else "error"
        )

    except Exception:
        dependencies["redis"] = "error"

    # ----------------------------------------------------------
    # LocalStack / STS
    # ----------------------------------------------------------
    try:
        sts = get_sts_client()

        response = sts.get_caller_identity()

        status_code = (
            response
            .get("ResponseMetadata", {})
            .get("HTTPStatusCode", 0)
        )

        dependencies["localstack"] = (
            "ok"
            if status_code == 200
            else "error"
        )

    except Exception:
        dependencies["localstack"] = "error"

    # ----------------------------------------------------------
    # S3
    # ----------------------------------------------------------
    try:
        s3 = get_s3_client()

        response = s3.list_buckets()

        status_code = (
            response
            .get("ResponseMetadata", {})
            .get("HTTPStatusCode", 0)
        )

        dependencies["s3"] = (
            "ok"
            if status_code == 200
            else "error"
        )

    except Exception:
        dependencies["s3"] = "error"

    # ----------------------------------------------------------
    # DynamoDB
    # ----------------------------------------------------------
    try:
        dynamodb = get_dynamodb_client()

        response = dynamodb.list_tables(
            Limit=1,
        )

        status_code = (
            response
            .get("ResponseMetadata", {})
            .get("HTTPStatusCode", 0)
        )

        dependencies["dynamodb"] = (
            "ok"
            if status_code == 200
            else "error"
        )

    except Exception:
        dependencies["dynamodb"] = "error"

    ready = all(
        status == "ok"
        for status in dependencies.values()
    )

    return {
        "status": (
            "ready"
            if ready
            else "not_ready"
        ),
        "dependencies": dependencies,
    }