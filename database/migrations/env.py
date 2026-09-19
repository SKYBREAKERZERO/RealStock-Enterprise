from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from libs.config import get_settings
from libs.database.credentials import (
    resolve_database_credentials,
)
from libs.database.models import Base

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _get_database_url() -> str:
    """
    Resolve the effective database URL used by Alembic.

    Local environments use DATABASE_URL / structured database
    configuration.

    Non-local environments may resolve credentials from
    AWS Secrets Manager.
    """

    settings = get_settings()

    credentials = resolve_database_credentials(
        settings
    )

    return credentials.database_url


def run_migrations_offline() -> None:
    database_url = _get_database_url()

    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={
            "paramstyle": "named",
        },
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    database_url = _get_database_url()

    connectable = create_engine(
        database_url,
        poolclass=pool.NullPool,
        connect_args={
            "connect_timeout": 5,
        },
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()