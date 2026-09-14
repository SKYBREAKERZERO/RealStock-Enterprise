import pytest
from fastapi.testclient import TestClient

from services.api.main import app

pytestmark = pytest.mark.integration

client = TestClient(app)


def test_health_endpoint() -> None:
    response = client.get(
        "/health"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "ok"


def test_readiness_endpoint() -> None:
    response = client.get(
        "/health/ready"
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["status"] == "ready"

    dependencies = payload[
        "dependencies"
    ]

    assert dependencies[
        "postgresql"
    ] == "ok"

    assert dependencies[
        "redis"
    ] == "ok"

    assert dependencies[
        "localstack"
    ] == "ok"

    assert dependencies[
        "s3"
    ] == "ok"

    assert dependencies[
        "dynamodb"
    ] == "ok"