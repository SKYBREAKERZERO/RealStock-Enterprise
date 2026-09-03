from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator
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

    database_url: str = Field(
        validation_alias="DATABASE_URL",
    )

    # ---------------------------------------------------------
    # Redis
    # ---------------------------------------------------------

    redis_url: str = Field(
        validation_alias="REDIS_URL",
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