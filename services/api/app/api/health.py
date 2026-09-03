from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from sqlalchemy import text

from libs.aws import get_sts_client
from libs.cache import get_redis_client
from libs.database import get_engine


router = APIRouter(
    tags=["health"],
)


@router.get("/health")
def health() -> dict[str, str]:
    """
    Liveness endpoint.

    This endpoint only confirms that the API process is running.
    """
    return {
        "status": "ok",
        "service": "realstock-api",
    }


@router.get("/health/ready")
def readiness() -> dict[str, Any]:
    """
    Readiness endpoint.

    Confirms that critical dependencies are reachable.
    """

    dependencies: dict[str, str] = {}

    # PostgreSQL
    try:
        engine = get_engine()

        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))

        dependencies["postgres"] = "ok"

    except Exception:
        dependencies["postgres"] = "error"

    # Redis
    try:
        redis = get_redis_client()

        dependencies["redis"] = (
            "ok"
            if redis.ping()
            else "error"
        )

    except Exception:
        dependencies["redis"] = "error"

    # LocalStack / AWS STS
    try:
        sts = get_sts_client()

        sts.get_caller_identity()

        dependencies["aws"] = "ok"

    except Exception:
        dependencies["aws"] = "error"

    ready = all(
        status == "ok"
        for status in dependencies.values()
    )

    return {
        "status": "ready" if ready else "not_ready",
        "dependencies": dependencies,
    }