from __future__ import annotations

from functools import lru_cache

from sqlalchemy import Engine, create_engine

from libs.config import get_settings
from libs.database.credentials import resolve_database_credentials


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """
    Return the process-wide SQLAlchemy engine.

    Database credentials are resolved once when the engine is first
    created. Local environments use local database configuration,
    while non-local environments may retrieve credentials from
    AWS Secrets Manager.

    The engine and its connection pool are then reused for the
    lifetime of the process.
    """

    settings = get_settings()

    credentials = resolve_database_credentials(
        settings
    )

    return create_engine(
        credentials.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        pool_timeout=10,
        pool_recycle=1800,
        connect_args={
            "connect_timeout": 5,
        },
    )