from __future__ import annotations

from uuid import uuid4

import pytest

from libs.cache import get_redis_client

pytestmark = pytest.mark.integration


def test_redis_ping() -> None:
    """
    Verify that the application can connect to Redis.
    """

    redis_client = get_redis_client()

    assert redis_client.ping() is True


def test_redis_set_get_delete_round_trip() -> None:
    """
    Verify basic Redis write/read/delete behavior.

    A unique key is used so parallel or repeated test runs
    do not interfere with each other.
    """

    redis_client = get_redis_client()

    key = (
        "realstock:test:"
        f"{uuid4()}"
    )

    value = "redis-integration-pass"

    try:
        result = redis_client.set(
            key,
            value,
            ex=30,
        )

        assert result is True

        stored_value = redis_client.get(
            key
        )

        assert stored_value == value

        ttl = redis_client.ttl(
            key
        )

        assert 0 < ttl <= 30

    finally:
        redis_client.delete(
            key
        )

    assert (
        redis_client.get(key)
        is None
    )