from __future__ import annotations

from fastapi import APIRouter, Response, status
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


# ============================================================
# Liveness
# ============================================================
#
# Purpose:
#   Indicates whether the API process itself is alive.
#
# Important:
#   This endpoint deliberately does NOT check external
#   dependencies.
#
# Docker / ECS container health checks should use this endpoint.
#
# Semantics:
#   200 -> application process is alive
# ============================================================
@router.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
    }


# ============================================================
# Readiness
# ============================================================
#
# Purpose:
#   Indicates whether the API is ready to serve traffic.
#
# Dependencies:
#   - PostgreSQL
#   - Redis
#   - AWS / LocalStack STS
#   - S3
#   - DynamoDB
#
# Semantics:
#
#   All dependencies available:
#       HTTP 200
#       status = ready
#
#   One or more dependencies unavailable:
#       HTTP 503
#       status = not_ready
#
# This distinction is important for ALB / ECS:
#
#   /health
#       process liveness
#
#   /health/ready
#       traffic readiness
#
# A temporary dependency failure should make the service
# unavailable for traffic without incorrectly declaring the
# container process itself dead.
# ============================================================
@router.get("/health/ready")
def readiness(
    response: Response,
) -> dict[str, object]:
    dependencies: dict[str, str] = {
        "postgresql": "unknown",
        "redis": "unknown",
        "localstack": "unknown",
        "s3": "unknown",
        "dynamodb": "unknown",
    }

    # ========================================================
    # PostgreSQL
    # ========================================================
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

    # ========================================================
    # Redis
    # ========================================================
    try:
        redis_client = get_redis_client()

        dependencies["redis"] = (
            "ok"
            if redis_client.ping()
            else "error"
        )

    except Exception:
        dependencies["redis"] = "error"

    # ========================================================
    # AWS / LocalStack STS
    # ========================================================
    try:
        sts_client = get_sts_client()

        aws_response = (
            sts_client.get_caller_identity()
        )

        status_code = (
            aws_response
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

    # ========================================================
    # S3
    # ========================================================
    try:
        s3_client = get_s3_client()

        aws_response = (
            s3_client.list_buckets()
        )

        status_code = (
            aws_response
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

    # ========================================================
    # DynamoDB
    # ========================================================
    try:
        dynamodb_client = (
            get_dynamodb_client()
        )

        aws_response = (
            dynamodb_client.list_tables(
                Limit=1,
            )
        )

        status_code = (
            aws_response
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

    # ========================================================
    # Aggregate readiness state
    # ========================================================
    ready = all(
        dependency_status == "ok"
        for dependency_status
        in dependencies.values()
    )

    # --------------------------------------------------------
    # HTTP readiness semantics
    # --------------------------------------------------------
    #
    # Returning HTTP 503 is important because infrastructure
    # such as an ALB should be able to determine readiness from
    # the HTTP status code without parsing the response body.
    # --------------------------------------------------------
    if not ready:
        response.status_code = (
            status.HTTP_503_SERVICE_UNAVAILABLE
        )

    return {
        "status": (
            "ready"
            if ready
            else "not_ready"
        ),
        "dependencies": dependencies,
    }