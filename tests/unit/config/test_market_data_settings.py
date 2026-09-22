from __future__ import annotations

import pytest
from pydantic import ValidationError

from libs.config.settings import Settings

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def isolate_market_data_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Isolate market-data settings from the developer machine.

    The user's shell may contain real MARKET_DATA_PROVIDER or
    TWELVE_DATA_API_KEY environment variables. Unit tests must
    never depend on those external values.
    """

    monkeypatch.delenv(
        "MARKET_DATA_PROVIDER",
        raising=False,
    )

    monkeypatch.delenv(
        "TWELVE_DATA_API_KEY",
        raising=False,
    )


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


def test_market_data_provider_defaults_to_mock() -> None:
    settings = _base_settings()

    assert settings.market_data_provider == "mock"
    assert settings.twelve_data_api_key is None


def test_twelve_data_provider_requires_api_key() -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "TWELVE_DATA_API_KEY is required when "
            "MARKET_DATA_PROVIDER=twelve_data"
        ),
    ):
        _base_settings(
            MARKET_DATA_PROVIDER="twelve_data",
        )


@pytest.mark.parametrize(
    "api_key",
    [
        "",
        " ",
        "   ",
    ],
)
def test_twelve_data_provider_rejects_blank_api_key(
    api_key: str,
) -> None:
    with pytest.raises(
        ValidationError,
        match=(
            "TWELVE_DATA_API_KEY is required when "
            "MARKET_DATA_PROVIDER=twelve_data"
        ),
    ):
        _base_settings(
            MARKET_DATA_PROVIDER="twelve_data",
            TWELVE_DATA_API_KEY=api_key,
        )


def test_twelve_data_provider_accepts_api_key() -> None:
    settings = _base_settings(
        MARKET_DATA_PROVIDER="twelve_data",
        TWELVE_DATA_API_KEY="test-api-key",
    )

    assert (
        settings.market_data_provider
        == "twelve_data"
    )

    assert settings.twelve_data_api_key is not None

    assert (
        settings.twelve_data_api_key
        .get_secret_value()
        == "test-api-key"
    )


def test_twelve_data_api_key_is_not_exposed_in_repr() -> None:
    api_key = (
        "super-secret-twelve-data-key"
    )

    settings = _base_settings(
        MARKET_DATA_PROVIDER="twelve_data",
        TWELVE_DATA_API_KEY=api_key,
    )

    representation = repr(
        settings
    )

    assert api_key not in representation


def test_mock_provider_does_not_require_api_key() -> None:
    settings = _base_settings(
        MARKET_DATA_PROVIDER="mock",
    )

    assert settings.market_data_provider == "mock"
    assert settings.twelve_data_api_key is None


def test_unknown_market_data_provider_is_rejected() -> None:
    with pytest.raises(
        ValidationError,
    ):
        _base_settings(
            MARKET_DATA_PROVIDER="unknown",
        )