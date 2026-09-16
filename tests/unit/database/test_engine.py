from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import libs.database.engine as engine_module

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def clear_engine_cache():
    engine_module.get_engine.cache_clear()

    yield

    engine_module.get_engine.cache_clear()


def test_get_engine_uses_resolved_credentials_and_safe_pool_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        app_env="local",
    )

    credentials = SimpleNamespace(
        database_url=(
            "postgresql+psycopg://"
            "realstock:secret"
            "@db.internal:5432/realstock"
            "?sslmode=require"
        ),
    )

    fake_engine = Mock(
        name="engine"
    )

    create_engine = Mock(
        return_value=fake_engine
    )

    resolve_database_credentials = Mock(
        return_value=credentials
    )

    monkeypatch.setattr(
        engine_module,
        "get_settings",
        lambda: settings,
    )

    monkeypatch.setattr(
        engine_module,
        "resolve_database_credentials",
        resolve_database_credentials,
    )

    monkeypatch.setattr(
        engine_module,
        "create_engine",
        create_engine,
    )

    result = engine_module.get_engine()

    assert result is fake_engine

    resolve_database_credentials.assert_called_once_with(
        settings
    )

    create_engine.assert_called_once_with(
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


def test_get_engine_is_cached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = SimpleNamespace(
        app_env="local",
    )

    credentials = SimpleNamespace(
        database_url=(
            "postgresql+psycopg://"
            "realstock:secret"
            "@db.internal:5432/realstock"
            "?sslmode=require"
        ),
    )

    fake_engine = Mock(
        name="engine"
    )

    create_engine = Mock(
        return_value=fake_engine
    )

    resolve_database_credentials = Mock(
        return_value=credentials
    )

    monkeypatch.setattr(
        engine_module,
        "get_settings",
        lambda: settings,
    )

    monkeypatch.setattr(
        engine_module,
        "resolve_database_credentials",
        resolve_database_credentials,
    )

    monkeypatch.setattr(
        engine_module,
        "create_engine",
        create_engine,
    )

    first = engine_module.get_engine()
    second = engine_module.get_engine()

    assert first is second

    resolve_database_credentials.assert_called_once_with(
        settings
    )

    create_engine.assert_called_once()