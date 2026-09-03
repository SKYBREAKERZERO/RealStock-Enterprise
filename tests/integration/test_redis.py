import pytest

from libs.cache import get_redis_client


pytestmark = pytest.mark.integration

TEST_KEY = "realstock:test:pytest"


def test_redis_ping() -> None:
    client = get_redis_client()

    assert client.ping() is True


def test_redis_set_get_delete() -> None:
    client = get_redis_client()

    try:
        result = client.set(
            TEST_KEY,
            "pytest-pass",
            ex=60,
        )

        assert result is True

        value = client.get(TEST_KEY)

        assert value == "pytest-pass"

        ttl = client.ttl(TEST_KEY)

        assert ttl > 0

    finally:
        client.delete(TEST_KEY)

    assert client.get(TEST_KEY) is None