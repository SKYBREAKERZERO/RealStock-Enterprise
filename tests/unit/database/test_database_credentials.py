from __future__ import annotations

import json
from typing import Literal
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError

from libs.config.settings import Settings
from libs.database.credentials import (
    DatabaseCredentialsError,
    resolve_database_credentials,
)

pytestmark = pytest.mark.unit


def _settings(
    *,
    app_env: Literal["local", "dev", "staging", "prod"] = "local",
    database_url: str | None = None,
) -> Settings:
    if database_url is None and app_env == "local":
        database_url = (
            "postgresql+psycopg://"
            "realstock:local-password"
            "@localhost:15432/realstock"
        )

    return Settings(
        _env_file=None,
        APP_ENV=app_env,
        AWS_REGION="ap-northeast-1",
        AWS_ENDPOINT_URL=(
            "http://localhost:4566"
            if app_env == "local"
            else None
        ),
        DATABASE_URL=database_url or "",
        DATABASE_SECRET_ID=(
            "realstock/test/database"
            if app_env != "local" and not database_url
            else None
        ),
        REDIS_URL="redis://localhost:6379/0",
    )


def _valid_secret() -> dict[str, object]:
    return {
        "engine": "postgres",
        "host": (
            "realstock.cluster-test."
            "ap-northeast-1.rds.amazonaws.com"
        ),
        "port": 5432,
        "dbname": "realstock",
        "username": "realstock_app",
        "password": "super-secret-password",
        "sslmode": "require",
    }


def test_local_environment_does_not_call_secrets_manager() -> None:
    client = Mock()

    credentials = resolve_database_credentials(
        _settings(app_env="local"),
        secret_id="should-not-be-used",
        secrets_client=client,
    )

    client.get_secret_value.assert_not_called()

    assert credentials.host == "localhost"
    assert credentials.port == 15432
    assert credentials.database == "realstock"
    assert credentials.username == "realstock"
    assert credentials.password == "local-password"
    assert credentials.sslmode is None


def test_non_local_environment_prefers_injected_database_url() -> None:
    client = Mock()

    database_url = (
        "postgresql+psycopg://"
        "realstock_app:ecs-secret-password"
        "@realstock-dev-database.proxy-test."
        "ap-northeast-1.rds.amazonaws.com:5432/realstock"
        "?sslmode=require"
    )

    credentials = resolve_database_credentials(
        _settings(
            app_env="dev",
            database_url=database_url,
        ),
        secret_id="should-not-be-used",
        secrets_client=client,
    )

    client.get_secret_value.assert_not_called()

    assert credentials.database == "realstock"
    assert credentials.username == "realstock_app"
    assert credentials.password == "ecs-secret-password"
    assert credentials.sslmode == "require"


def test_non_local_environment_reads_secrets_manager() -> None:
    client = Mock()

    client.get_secret_value.return_value = {
        "SecretString": json.dumps(_valid_secret())
    }

    credentials = resolve_database_credentials(
        _settings(app_env="dev", database_url=""),
        secret_id="realstock/dev/database",
        secrets_client=client,
    )

    client.get_secret_value.assert_called_once_with(
        SecretId="realstock/dev/database"
    )

    assert credentials.host == (
        "realstock.cluster-test."
        "ap-northeast-1.rds.amazonaws.com"
    )
    assert credentials.port == 5432
    assert credentials.database == "realstock"
    assert credentials.username == "realstock_app"
    assert credentials.password == "super-secret-password"
    assert credentials.sslmode == "require"


def test_database_secret_builds_safe_database_url() -> None:
    client = Mock()

    secret = _valid_secret()
    secret["username"] = "user@example.com"
    secret["password"] = "p@ss:word/test"

    client.get_secret_value.return_value = {
        "SecretString": json.dumps(secret)
    }

    credentials = resolve_database_credentials(
        _settings(app_env="prod", database_url=""),
        secret_id="realstock/prod/database",
        secrets_client=client,
    )

    assert "user%40example.com" in credentials.database_url
    assert "p%40ss%3Aword%2Ftest" in credentials.database_url
    assert credentials.database_url.endswith(
        "?sslmode=require"
    )


def test_database_secret_requires_complete_credentials() -> None:
    client = Mock()

    secret = _valid_secret()
    del secret["password"]

    client.get_secret_value.return_value = {
        "SecretString": json.dumps(secret)
    }

    with pytest.raises(
        DatabaseCredentialsError,
        match="missing required fields",
    ):
        resolve_database_credentials(
            _settings(app_env="dev"),
            secret_id="realstock/dev/database",
            secrets_client=client,
        )


def test_invalid_secret_json_fails_fast() -> None:
    client = Mock()

    client.get_secret_value.return_value = {
        "SecretString": "{invalid-json"
    }

    with pytest.raises(
        DatabaseCredentialsError,
        match="invalid JSON",
    ):
        resolve_database_credentials(
            _settings(app_env="dev"),
            secret_id="realstock/dev/database",
            secrets_client=client,
        )


def test_secrets_manager_failure_does_not_fallback() -> None:
    client = Mock()

    aws_error = ClientError(
        error_response={
            "Error": {
                "Code": "AccessDeniedException",
                "Message": "Access denied",
            }
        },
        operation_name="GetSecretValue",
    )

    client.get_secret_value.side_effect = aws_error

    with pytest.raises(
        DatabaseCredentialsError,
        match="Unable to retrieve database credentials",
    ) as exc_info:
        resolve_database_credentials(
            _settings(app_env="prod"),
            secret_id="realstock/prod/database",
            secrets_client=client,
        )

    assert exc_info.value.__cause__ is aws_error


def test_database_credentials_repr_does_not_expose_password() -> None:
    client = Mock()

    client.get_secret_value.return_value = {
        "SecretString": json.dumps(_valid_secret())
    }

    credentials = resolve_database_credentials(
        _settings(app_env="dev", database_url=""),
        secret_id="realstock/dev/database",
        secrets_client=client,
    )

    rendered = repr(credentials)

    assert "super-secret-password" not in rendered
    assert "<redacted>" in rendered


def test_database_secret_id_is_available_from_settings() -> None:
    settings = Settings(
        _env_file=None,
        APP_ENV="dev",
        AWS_REGION="ap-northeast-1",
        DATABASE_SECRET_ID="realstock/dev/database",
        REDIS_URL="redis://localhost:6379/0",
    )

    assert (
        settings.database_secret_id
        == "realstock/dev/database"
    )


def test_non_local_settings_support_secret_only_database_configuration() -> None:
    settings = Settings(
        _env_file=None,
        APP_ENV="prod",
        AWS_REGION="ap-northeast-1",
        DATABASE_SECRET_ID="realstock/prod/database",
        REDIS_URL="redis://localhost:6379/0",
    )

    assert (
        settings.database_secret_id
        == "realstock/prod/database"
    )
    assert settings.database_url == ""


def test_resolver_uses_secret_id_from_settings() -> None:
    client = Mock()

    client.get_secret_value.return_value = {
        "SecretString": json.dumps(_valid_secret())
    }

    settings = Settings(
        _env_file=None,
        APP_ENV="dev",
        AWS_REGION="ap-northeast-1",
        DATABASE_SECRET_ID="realstock/dev/database",
        REDIS_URL="redis://localhost:6379/0",
    )

    credentials = resolve_database_credentials(
        settings,
        secrets_client=client,
    )

    client.get_secret_value.assert_called_once_with(
        SecretId="realstock/dev/database"
    )

    assert credentials.database == "realstock"
    assert credentials.username == "realstock_app"


def test_explicit_secret_id_overrides_settings_secret_id() -> None:
    client = Mock()

    client.get_secret_value.return_value = {
        "SecretString": json.dumps(_valid_secret())
    }

    settings = Settings(
        _env_file=None,
        APP_ENV="dev",
        AWS_REGION="ap-northeast-1",
        DATABASE_SECRET_ID="realstock/dev/default-database",
        REDIS_URL="redis://localhost:6379/0",
    )

    resolve_database_credentials(
        settings,
        secret_id="realstock/dev/override-database",
        secrets_client=client,
    )

    client.get_secret_value.assert_called_once_with(
        SecretId="realstock/dev/override-database"
    )

