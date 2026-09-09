from fastapi import Response, status

from services.api.routes import health as health_routes


def _raise_dependency_error():
    raise RuntimeError("dependency unavailable")


def test_readiness_returns_503_when_all_dependencies_fail(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        health_routes,
        "get_engine",
        _raise_dependency_error,
    )

    monkeypatch.setattr(
        health_routes,
        "get_redis_client",
        _raise_dependency_error,
    )

    monkeypatch.setattr(
        health_routes,
        "get_sts_client",
        _raise_dependency_error,
    )

    monkeypatch.setattr(
        health_routes,
        "get_s3_client",
        _raise_dependency_error,
    )

    monkeypatch.setattr(
        health_routes,
        "get_dynamodb_client",
        _raise_dependency_error,
    )

    response = Response()

    payload = health_routes.readiness(
        response=response,
    )

    assert (
        response.status_code
        == status.HTTP_503_SERVICE_UNAVAILABLE
    )

    assert payload["status"] == "not_ready"

    assert payload["dependencies"] == {
        "postgresql": "error",
        "redis": "error",
        "localstack": "error",
        "s3": "error",
        "dynamodb": "error",
    }


def test_readiness_returns_200_when_all_dependencies_succeed(
    monkeypatch,
) -> None:
    class FakeDatabaseResult:
        def scalar_one(self):
            return 1

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(
            self,
            exc_type,
            exc,
            traceback,
        ):
            return None

        def execute(
            self,
            statement,
        ):
            return FakeDatabaseResult()

    class FakeEngine:
        def connect(self):
            return FakeConnection()

    class FakeRedis:
        def ping(self):
            return True

    class FakeAwsClient:
        def get_caller_identity(self):
            return {
                "ResponseMetadata": {
                    "HTTPStatusCode": 200,
                },
            }

        def list_buckets(self):
            return {
                "ResponseMetadata": {
                    "HTTPStatusCode": 200,
                },
            }

        def list_tables(
            self,
            Limit,
        ):
            return {
                "ResponseMetadata": {
                    "HTTPStatusCode": 200,
                },
            }

    monkeypatch.setattr(
        health_routes,
        "get_engine",
        lambda: FakeEngine(),
    )

    monkeypatch.setattr(
        health_routes,
        "get_redis_client",
        lambda: FakeRedis(),
    )

    monkeypatch.setattr(
        health_routes,
        "get_sts_client",
        lambda: FakeAwsClient(),
    )

    monkeypatch.setattr(
        health_routes,
        "get_s3_client",
        lambda: FakeAwsClient(),
    )

    monkeypatch.setattr(
        health_routes,
        "get_dynamodb_client",
        lambda: FakeAwsClient(),
    )

    response = Response()

    payload = health_routes.readiness(
        response=response,
    )

    assert (
        response.status_code
        == status.HTTP_200_OK
    )

    assert payload["status"] == "ready"

    assert payload["dependencies"] == {
        "postgresql": "ok",
        "redis": "ok",
        "localstack": "ok",
        "s3": "ok",
        "dynamodb": "ok",
    }