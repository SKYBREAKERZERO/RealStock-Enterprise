from __future__ import annotations

import pytest
from pydantic import ValidationError

from libs.config.settings import Settings

pytestmark = pytest.mark.unit


def _base_settings(
    **overrides: object,
) -> Settings:
    values: dict[str, object] = {
        "APP_ENV": "local",
        "AWS_ENDPOINT_URL": "http://localhost:4566",
        "DATABASE_URL": (
            "postgresql+psycopg://"
            "realstock:realstock_local_password"
            "@localhost:15432/realstock"
        ),
        "REDIS_URL": "redis://localhost:6379/0",
    }

    values.update(overrides)

    return Settings(
        _env_file=None,
        **values,
    )


def test_outbox_settings_have_safe_defaults() -> None:
    settings = _base_settings()

    assert settings.outbox_batch_size == 10
    assert settings.outbox_lease_seconds == 60
    assert settings.outbox_poll_interval_seconds == 1.0
    assert settings.outbox_error_backoff_seconds == 5.0
    assert settings.outbox_event_bus_name == "default"
    assert settings.outbox_metrics_namespace == "RealStock/Outbox"
    assert settings.outbox_metrics_interval_seconds == 30


def test_outbox_settings_can_be_overridden() -> None:
    settings = _base_settings(
        OUTBOX_BATCH_SIZE="50",
        OUTBOX_LEASE_SECONDS="120",
        OUTBOX_POLL_INTERVAL_SECONDS="2.5",
        OUTBOX_ERROR_BACKOFF_SECONDS="10",
        OUTBOX_EVENT_BUS_NAME="realstock-events",
        OUTBOX_METRICS_NAMESPACE="RealStock/TestOutbox",
        OUTBOX_METRICS_INTERVAL_SECONDS="60",
    )

    assert settings.outbox_batch_size == 50
    assert settings.outbox_lease_seconds == 120
    assert settings.outbox_poll_interval_seconds == 2.5
    assert settings.outbox_error_backoff_seconds == 10.0
    assert settings.outbox_event_bus_name == "realstock-events"
    assert (
        settings.outbox_metrics_namespace
        == "RealStock/TestOutbox"
    )
    assert settings.outbox_metrics_interval_seconds == 60


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1", 1),
        ("1000", 1000),
    ],
)
def test_outbox_batch_size_accepts_boundaries(
    value: str,
    expected: int,
) -> None:
    settings = _base_settings(
        OUTBOX_BATCH_SIZE=value,
    )

    assert settings.outbox_batch_size == expected


@pytest.mark.parametrize(
    "value",
    [
        "0",
        "-1",
        "1001",
    ],
)
def test_outbox_batch_size_rejects_invalid_values(
    value: str,
) -> None:
    with pytest.raises(ValidationError):
        _base_settings(
            OUTBOX_BATCH_SIZE=value,
        )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1", 1),
        ("3600", 3600),
    ],
)
def test_outbox_lease_seconds_accepts_boundaries(
    value: str,
    expected: int,
) -> None:
    settings = _base_settings(
        OUTBOX_LEASE_SECONDS=value,
    )

    assert settings.outbox_lease_seconds == expected


@pytest.mark.parametrize(
    "value",
    [
        "0",
        "-1",
        "3601",
    ],
)
def test_outbox_lease_seconds_rejects_invalid_values(
    value: str,
) -> None:
    with pytest.raises(ValidationError):
        _base_settings(
            OUTBOX_LEASE_SECONDS=value,
        )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0.1", 0.1),
        ("60", 60.0),
    ],
)
def test_outbox_poll_interval_accepts_valid_values(
    value: str,
    expected: float,
) -> None:
    settings = _base_settings(
        OUTBOX_POLL_INTERVAL_SECONDS=value,
    )

    assert settings.outbox_poll_interval_seconds == expected


@pytest.mark.parametrize(
    "value",
    [
        "0",
        "-1",
        "60.1",
    ],
)
def test_outbox_poll_interval_rejects_invalid_values(
    value: str,
) -> None:
    with pytest.raises(ValidationError):
        _base_settings(
            OUTBOX_POLL_INTERVAL_SECONDS=value,
        )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0.1", 0.1),
        ("300", 300.0),
    ],
)
def test_outbox_error_backoff_accepts_valid_values(
    value: str,
    expected: float,
) -> None:
    settings = _base_settings(
        OUTBOX_ERROR_BACKOFF_SECONDS=value,
    )

    assert settings.outbox_error_backoff_seconds == expected


@pytest.mark.parametrize(
    "value",
    [
        "0",
        "-1",
        "300.1",
    ],
)
def test_outbox_error_backoff_rejects_invalid_values(
    value: str,
) -> None:
    with pytest.raises(ValidationError):
        _base_settings(
            OUTBOX_ERROR_BACKOFF_SECONDS=value,
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        (
            "OUTBOX_EVENT_BUS_NAME",
            "",
        ),
        (
            "OUTBOX_METRICS_NAMESPACE",
            "",
        ),
    ],
)
def test_outbox_names_must_not_be_empty(
    field: str,
    value: str,
) -> None:
    with pytest.raises(ValidationError):
        _base_settings(
            **{
                field: value,
            }
        )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1", 1),
        ("3600", 3600),
    ],
)
def test_outbox_metrics_interval_accepts_boundaries(
    value: str,
    expected: int,
) -> None:
    settings = _base_settings(
        OUTBOX_METRICS_INTERVAL_SECONDS=value,
    )

    assert (
        settings.outbox_metrics_interval_seconds
        == expected
    )


@pytest.mark.parametrize(
    "value",
    [
        "0",
        "-1",
        "3601",
    ],
)
def test_outbox_metrics_interval_rejects_invalid_values(
    value: str,
) -> None:
    with pytest.raises(ValidationError):
        _base_settings(
            OUTBOX_METRICS_INTERVAL_SECONDS=value,
        )