from __future__ import annotations

from functools import lru_cache

from sqlalchemy import Engine, create_engine

from libs.config import get_settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    settings = get_settings()

    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_timeout=10,
        pool_recycle=1800,
        connect_args={
            "connect_timeout": 5,
        },
    )