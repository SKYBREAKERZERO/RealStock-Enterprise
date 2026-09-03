import pytest
from libs.config import get_settings

pytestmark = pytest.mark.unit

def test_settings_load_local_environment() -> None:
    settings = get_settings()

    assert settings.app_name == "realstock"
    assert settings.app_env == "local"
    assert settings.aws_region == "ap-northeast-1"

def test_local_environment_uses_localstack() -> None:
    settings = get_settings()

    assert settings.use_localstack is True
    assert settings.aws_endpoint_url is not None
    assert settings.aws_endpoint_url.startswith("http://")

def test_database_configuration_exists() -> None:
    settings = get_settings()

    assert settings.database_url
    assert "postgresql+psycopg://" in settings.database_url

def test_redis_configuration_exists() -> None:
    settings = get_settings()

    assert settings.redis_url
    assert settings.redis_url.startswith("redis://")