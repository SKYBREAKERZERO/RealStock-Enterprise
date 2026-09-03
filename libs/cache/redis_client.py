from __future__ import annotations

from functools import lru_cache

from redis import Redis

from libs.config import get_settings


@lru_cache(maxsize=1)
def get_redis_client() -> Redis:
    """
    Return one cached Redis client per Python process.

    Local:
        Docker Redis -> localhost:6379

    AWS:
        Amazon ElastiCache for Redis
    """

    settings = get_settings()

    return Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
        health_check_interval=30,
    )