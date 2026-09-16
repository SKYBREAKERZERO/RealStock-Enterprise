from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal
from urllib.parse import quote_plus

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """
    Central application configuration for RealStock Enterprise.

    Configuration priority:
    1. Operating-system environment variables
    2. Project root .env file
    3. Field defaults

    Secrets must never be hard-coded in application code.
    """

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        frozen=True,
    )

    # ---------------------------------------------------------
    # Application
    # ---------------------------------------------------------

    app_name: str = Field(
        default="realstock",
        validation_alias="APP_NAME",
    )

    app_env: Literal[
        "local",
        "dev",
        "staging",
        "prod",
    ] = Field(
        default="local",
        validation_alias="APP_ENV",
    )

    log_level: Literal[
        "DEBUG",
        "INFO",
        "WARNING",
        "ERROR",
        "CRITICAL",
    ] = Field(
        default="INFO",
        validation_alias="LOG_LEVEL",
    )

    # ---------------------------------------------------------
    # AWS / LocalStack
    # ---------------------------------------------------------

    aws_region: str = Field(
        default="ap-northeast-1",
        validation_alias="AWS_REGION",
    )

    aws_endpoint_url: str | None = Field(
        default=None,
        validation_alias="AWS_ENDPOINT_URL",
    )

    # ---------------------------------------------------------
    # PostgreSQL
    # ---------------------------------------------------------

    # AWS Secrets Manager secret identifier.
    #
    # Intended for dev/staging/prod environments where database
    # credentials are retrieved at runtime rather than stored
    # directly in application environment variables.
    database_secret_id: str | None = Field(
        default=None,
        validation_alias="DATABASE_SECRET_ID",
    )

    # Legacy database configuration.
    #
    # DATABASE_URL remains supported for backward compatibility,
    # local development, tests, and gradual migration.
    #
    # When structured DATABASE_* values are supplied, they take
    # precedence and database_url is derived automatically.
    database_url: str = Field(
        default="",
        validation_alias="DATABASE_URL",
        repr=False,
    )

    database_host: str | None = Field(
        default=None,
        validation_alias="DATABASE_HOST",
    )

    database_port: int = Field(
        default=5432,
        ge=1,
        le=65535,
        validation_alias="DATABASE_PORT",
    )

    database_name: str | None = Field(
        default=None,
        validation_alias="DATABASE_NAME",
    )

    database_username: str | None = Field(
        default=None,
        validation_alias="DATABASE_USERNAME",
    )

    database_password: SecretStr | None = Field(
        default=None,
        validation_alias="DATABASE_PASSWORD",
        repr=False,
    )

    database_sslmode: str = Field(
        default="require",
        min_length=1,
        validation_alias="DATABASE_SSLMODE",
    )

    # ---------------------------------------------------------
    # Redis
    # ---------------------------------------------------------

    redis_url: str = Field(
        validation_alias="REDIS_URL",
    )

    # ---------------------------------------------------------
    # Database validation / resolution
    # ---------------------------------------------------------

    @model_validator(mode="after")
    def validate_database_configuration(self) -> Settings:
        """
        Validate supported database configuration modes.

        Supported modes:

        1. Legacy DATABASE_URL
        2. Structured DATABASE_* configuration
        3. DATABASE_SECRET_ID for non-local AWS environments

        Structured DATABASE_* configuration takes precedence over
        DATABASE_URL when any structured credential field is supplied.

        Settings does not access AWS Secrets Manager directly.
        DATABASE_SECRET_ID only identifies the secret that the database
        credential resolver will retrieve later.
        """

        structured_database_configured = any(
            value is not None
            for value in (
                self.database_host,
                self.database_name,
                self.database_username,
                self.database_password,
            )
        )

        secret_configured = bool(
            self.database_secret_id
            and self.database_secret_id.strip()
        )

        # -----------------------------------------------------
        # Structured DATABASE_* mode
        # -----------------------------------------------------

        if structured_database_configured:
            missing_fields: list[str] = []

            if (
                self.database_host is None
                or not self.database_host.strip()
            ):
                missing_fields.append("DATABASE_HOST")

            if (
                self.database_name is None
                or not self.database_name.strip()
            ):
                missing_fields.append("DATABASE_NAME")

            if (
                self.database_username is None
                or not self.database_username.strip()
            ):
                missing_fields.append("DATABASE_USERNAME")

            if (
                self.database_password is None
                or not self.database_password.get_secret_value()
            ):
                missing_fields.append("DATABASE_PASSWORD")

            if missing_fields:
                raise ValueError(
                    "Incomplete structured database configuration. "
                    f"Missing: {', '.join(missing_fields)}"
                )

            # The checks above guarantee these values are populated.
            assert self.database_host is not None
            assert self.database_name is not None
            assert self.database_username is not None
            assert self.database_password is not None

            host = self.database_host.strip()
            database_name = quote_plus(
                self.database_name.strip()
            )
            username = quote_plus(
                self.database_username.strip()
            )
            password = quote_plus(
                self.database_password.get_secret_value()
            )
            sslmode = quote_plus(
                self.database_sslmode.strip()
            )

            resolved_database_url = (
                "postgresql+psycopg://"
                f"{username}:{password}"
                f"@{host}:{self.database_port}"
                f"/{database_name}"
                f"?sslmode={sslmode}"
            )

            # Settings is frozen to prevent accidental runtime
            # mutation. This controlled assignment resolves the
            # effective URL during model construction.
            object.__setattr__(
                self,
                "database_url",
                resolved_database_url,
            )

            return self

        # -----------------------------------------------------
        # AWS Secrets Manager mode
        # -----------------------------------------------------

        if secret_configured:
            if self.app_env == "local":
                if not self.database_url.strip():
                    raise ValueError(
                        "Local environments require DATABASE_URL or "
                        "structured DATABASE_* configuration. "
                        "DATABASE_SECRET_ID alone is not sufficient."
                    )

                return self

            # Non-local environments may intentionally have no
            # DATABASE_URL. credentials.py will retrieve the secret
            # and construct the effective database URL.
            return self

        # -----------------------------------------------------
        # Legacy DATABASE_URL mode
        # -----------------------------------------------------

        if self.database_url.strip():
            return self

        # -----------------------------------------------------
        # No valid database configuration
        # -----------------------------------------------------

        raise ValueError(
            "Database configuration is required. Provide DATABASE_URL, "
            "structured DATABASE_* configuration, or DATABASE_SECRET_ID "
            "for a non-local environment."
        )

    # ---------------------------------------------------------
    # Environment validation
    # ---------------------------------------------------------

    @model_validator(mode="after")
    def validate_environment(self) -> Settings:
        """
        Validate environment-specific configuration.

        Local development must use LocalStack.
        Non-local environments must not point to LocalStack.
        """

        if self.app_env == "local":
            if not self.aws_endpoint_url:
                raise ValueError(
                    "AWS_ENDPOINT_URL is required when APP_ENV=local"
                )

        else:
            if self.aws_endpoint_url:
                raise ValueError(
                    "AWS_ENDPOINT_URL must not be configured "
                    "outside the local environment"
                )

        return self

    # ---------------------------------------------------------
    # Environment helpers
    # ---------------------------------------------------------

    @property
    def is_local(self) -> bool:
        return self.app_env == "local"

    @property
    def is_development(self) -> bool:
        return self.app_env == "dev"

    @property
    def is_staging(self) -> bool:
        return self.app_env == "staging"

    @property
    def is_production(self) -> bool:
        return self.app_env == "prod"

    @property
    def use_localstack(self) -> bool:
        return (
            self.is_local
            and bool(self.aws_endpoint_url)
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Return one immutable cached Settings instance per Python process.
    """

    return Settings()