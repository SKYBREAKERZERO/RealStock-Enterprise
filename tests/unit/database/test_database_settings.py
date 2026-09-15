from __future__ import annotations

import pytest

from libs.config.settings import Settings

pytestmark = pytest.mark.unit

def _base_environment() -> dict[str, str]:
    return {
        "APP_ENV": "local",
        "AWS_ENDPOINT_URL": "http://localhost:4566",
    }

def test_database_url_can_be_derived_from_structured_settings() -> None:
    settings = Settings(
        **_base_environment(),
        DATABASE_HOST="postgres",
        DATABASE_PORT="5432",
        DATABASE_NAME="realstock",
        DATABASE_USERNAME="realstock",
        DATABASE_PASSWORD="secret",
        DATABASE_SSLMODE="require",
    )

    assert settings.database_host == "postgres"
    assert settings.database_port == 5432
    assert settings.database_name == "realstock"
    assert settings.database_username == "realstock"
    assert settings.database_sslmode == "require"

    assert settings.database_url == (
        "postgresql+psycopg://"
        "realstock:secret@postgres:5432/"
        "realstock?sslmode=require"
    )

def test_database_url_escapes_credentials() -> None:
    settings = Settings(
        **_base_environment(),
        DATABASE_HOST="postgres",
        DATABASE_PORT="5432",
        DATABASE_NAME="realstock",
        DATABASE_USERNAME="user@example.com",
        DATABASE_PASSWORD="p@ss:word/test",
        DATABASE_SSLMODE="require",
    )

    assert "user%40example.com" in settings.database_url
    assert "p%40ss%3Aword%2Ftest" in settings.database_url

def test_database_url_legacy_value_remains_supported() -> None:
    legacy_url = (
        "postgresql+psycopg://"
        "realstock:local@localhost:15432/realstock"
    )

    settings = Settings(
        **_base_environment(),
        DATABASE_URL=legacy_url,
    )

    assert settings.database_url == legacy_url

def test_structured_database_config_requires_complete_credentials() -> None:
    with pytest.raises(ValueError):
        Settings(
            **_base_environment(),
            DATABASE_HOST="postgres",
            DATABASE_NAME="realstock",
            DATABASE_USERNAME="realstock",
        )

def test_database_port_must_be_valid() -> None:
    with pytest.raises(ValueError):
        Settings(
            **_base_environment(),
            DATABASE_HOST="postgres",
            DATABASE_PORT="70000",
            DATABASE_NAME="realstock",
            DATABASE_USERNAME="realstock",
            DATABASE_PASSWORD="secret",
        )

def test_database_password_is_not_exposed_in_repr() -> None:
    settings = Settings(
        **_base_environment(),
        DATABASE_HOST="postgres",
        DATABASE_PORT="5432",
        DATABASE_NAME="realstock",
        DATABASE_USERNAME="realstock",
        DATABASE_PASSWORD="super-secret-value",
        DATABASE_SSLMODE="require",
    )

    assert "super-secret-value" not in repr(settings)