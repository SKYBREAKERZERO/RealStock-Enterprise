from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol
from urllib.parse import quote_plus

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy.engine import make_url

from libs.config.settings import Settings


class DatabaseCredentialsError(RuntimeError):
    """Raised when database credentials cannot be resolved safely."""


class SecretsManagerClient(Protocol):
    """Minimal AWS Secrets Manager client interface."""

    def get_secret_value(
        self,
        *,
        SecretId: str,
    ) -> dict[str, Any]:
        """Return one secret value."""


@dataclass(frozen=True, slots=True, repr=False)
class DatabaseCredentials:
    """
    Normalized PostgreSQL database credentials.

    Password values are deliberately excluded from repr().
    """

    host: str
    port: int
    database: str
    username: str
    password: str
    sslmode: str | None = None

    def __post_init__(self) -> None:
        if not self.host.strip():
            raise DatabaseCredentialsError(
                "Database host must not be empty."
            )

        if not 1 <= self.port <= 65535:
            raise DatabaseCredentialsError(
                "Database port must be between 1 and 65535."
            )

        if not self.database.strip():
            raise DatabaseCredentialsError(
                "Database name must not be empty."
            )

        if not self.username.strip():
            raise DatabaseCredentialsError(
                "Database username must not be empty."
            )

        if not self.password:
            raise DatabaseCredentialsError(
                "Database password must not be empty."
            )

        if (
            self.sslmode is not None
            and not self.sslmode.strip()
        ):
            raise DatabaseCredentialsError(
                "Database sslmode must not be empty."
            )

    def __repr__(self) -> str:
        return (
            "DatabaseCredentials("
            f"host={self.host!r}, "
            f"port={self.port!r}, "
            f"database={self.database!r}, "
            f"username={self.username!r}, "
            "password=<redacted>, "
            f"sslmode={self.sslmode!r}"
            ")"
        )

    @property
    def database_url(self) -> str:
        """Build an escaped SQLAlchemy PostgreSQL URL."""

        username = quote_plus(self.username)
        password = quote_plus(self.password)
        database = quote_plus(self.database)

        url = (
            "postgresql+psycopg://"
            f"{username}:{password}"
            f"@{self.host}:{self.port}"
            f"/{database}"
        )

        if self.sslmode is not None:
            sslmode = quote_plus(self.sslmode)

            url = (
                f"{url}"
                f"?sslmode={sslmode}"
            )

        return url

    @classmethod
    def from_database_url(
        cls,
        database_url: str,
    ) -> DatabaseCredentials:
        """
        Parse credentials from an existing SQLAlchemy database URL.

        Primarily used for local development.
        """

        if not database_url.strip():
            raise DatabaseCredentialsError(
                "DATABASE_URL must not be empty."
            )

        try:
            parsed_url = make_url(database_url)
        except Exception as exc:
            raise DatabaseCredentialsError(
                "DATABASE_URL is invalid."
            ) from exc

        if parsed_url.host is None:
            raise DatabaseCredentialsError(
                "DATABASE_URL does not contain a database host."
            )

        if parsed_url.database is None:
            raise DatabaseCredentialsError(
                "DATABASE_URL does not contain a database name."
            )

        if parsed_url.username is None:
            raise DatabaseCredentialsError(
                "DATABASE_URL does not contain a database username."
            )

        if parsed_url.password is None:
            raise DatabaseCredentialsError(
                "DATABASE_URL does not contain a database password."
            )

        sslmode_value = parsed_url.query.get("sslmode")

        sslmode = (
            sslmode_value
            if isinstance(sslmode_value, str)
            else None
        )

        return cls(
            host=parsed_url.host,
            port=parsed_url.port or 5432,
            database=parsed_url.database,
            username=parsed_url.username,
            password=parsed_url.password,
            sslmode=sslmode,
        )


def resolve_database_credentials(
    settings: Settings,
    *,
    secret_id: str | None = None,
    secrets_client: SecretsManagerClient | None = None,
) -> DatabaseCredentials:
    """
    Resolve effective database credentials.

    DATABASE_URL is preferred whenever it is already available.

    This supports both:
    - local development, where DATABASE_URL is configured directly;
    - ECS secret injection, where AWS Secrets Manager injects
      DATABASE_URL into the container environment.

    When DATABASE_URL is unavailable, non-local environments may
    resolve structured credentials from AWS Secrets Manager by using
    DATABASE_SECRET_ID.

    Secret ID priority:
        explicit secret_id
        >
        settings.database_secret_id
    """

    if settings.database_url.strip():
        return DatabaseCredentials.from_database_url(
            settings.database_url
        )

    if settings.is_local:
        raise DatabaseCredentialsError(
            "Local environments require DATABASE_URL."
        )

    resolved_secret_id = (
        secret_id
        or settings.database_secret_id
    )

    if (
        resolved_secret_id is None
        or not resolved_secret_id.strip()
    ):
        raise DatabaseCredentialsError(
            "A Secrets Manager secret ID is required "
            "outside the local environment."
        )

    resolved_secret_id = resolved_secret_id.strip()

    client = secrets_client

    if client is None:
        client = boto3.client(
            "secretsmanager",
            region_name=settings.aws_region,
        )

    try:
        response = client.get_secret_value(
            SecretId=resolved_secret_id,
        )
    except (BotoCoreError, ClientError) as exc:
        raise DatabaseCredentialsError(
            "Unable to retrieve database credentials "
            "from Secrets Manager secret "
            f"{resolved_secret_id!r}."
        ) from exc

    secret_string = response.get("SecretString")

    if (
        not isinstance(secret_string, str)
        or not secret_string.strip()
    ):
        raise DatabaseCredentialsError(
            "Database secret must contain "
            "a non-empty SecretString."
        )

    try:
        payload = json.loads(secret_string)
    except json.JSONDecodeError as exc:
        raise DatabaseCredentialsError(
            "Database secret contains invalid JSON."
        ) from exc

    if not isinstance(payload, dict):
        raise DatabaseCredentialsError(
            "Database secret JSON must be an object."
        )

    return _credentials_from_secret_payload(
        payload
    )


def _credentials_from_secret_payload(
    payload: dict[str, Any],
) -> DatabaseCredentials:
    """Normalize an AWS Secrets Manager PostgreSQL secret."""

    engine = payload.get("engine")

    if engine is not None:
        normalized_engine = (
            str(engine)
            .strip()
            .lower()
        )

        if normalized_engine not in {
            "postgres",
            "postgresql",
        }:
            raise DatabaseCredentialsError(
                "Database secret engine "
                "must be PostgreSQL."
            )

    database = payload.get("dbname")

    if database is None:
        database = payload.get("database")

    required_values = {
        "host": payload.get("host"),
        "port": payload.get("port"),
        "dbname": database,
        "username": payload.get("username"),
        "password": payload.get("password"),
    }

    missing_fields = [
        name
        for name, value in required_values.items()
        if value is None or value == ""
    ]

    if missing_fields:
        raise DatabaseCredentialsError(
            "Database secret is missing "
            "required fields: "
            f"{', '.join(missing_fields)}"
        )

    try:
        port = int(
            required_values["port"]
        )
    except (TypeError, ValueError) as exc:
        raise DatabaseCredentialsError(
            "Database secret port "
            "must be an integer."
        ) from exc

    sslmode_value = payload.get(
        "sslmode",
        "require",
    )

    if not isinstance(sslmode_value, str):
        raise DatabaseCredentialsError(
            "Database secret sslmode "
            "must be a string."
        )

    return DatabaseCredentials(
        host=str(
            required_values["host"]
        ).strip(),
        port=port,
        database=str(
            required_values["dbname"]
        ).strip(),
        username=str(
            required_values["username"]
        ).strip(),
        password=str(
            required_values["password"]
        ),
        sslmode=sslmode_value.strip(),
    )