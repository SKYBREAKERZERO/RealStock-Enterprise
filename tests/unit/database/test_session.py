from __future__ import annotations

from unittest.mock import MagicMock, Mock

import pytest
from sqlalchemy.orm import Session

import libs.database.session as session_module

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def clear_session_factory_cache():
    session_module.get_session_factory.cache_clear()
    yield
    session_module.get_session_factory.cache_clear()


def test_session_factory_uses_shared_engine(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_engine = Mock(name="engine")
    fake_factory = Mock(name="session_factory")
    sessionmaker = Mock(return_value=fake_factory)

    monkeypatch.setattr(
        session_module,
        "get_engine",
        lambda: fake_engine,
    )
    monkeypatch.setattr(
        session_module,
        "sessionmaker",
        sessionmaker,
    )

    result = session_module.get_session_factory()

    assert result is fake_factory

    sessionmaker.assert_called_once_with(
        bind=fake_engine,
        class_=Session,
        autoflush=False,
        expire_on_commit=False,
    )


def test_session_factory_is_cached(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_engine = Mock(name="engine")
    fake_factory = Mock(name="session_factory")
    sessionmaker = Mock(return_value=fake_factory)

    monkeypatch.setattr(
        session_module,
        "get_engine",
        lambda: fake_engine,
    )
    monkeypatch.setattr(
        session_module,
        "sessionmaker",
        sessionmaker,
    )

    first = session_module.get_session_factory()
    second = session_module.get_session_factory()

    assert first is second
    sessionmaker.assert_called_once()


def test_get_db_session_closes_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    managed_session = MagicMock(name="managed_session")
    yielded_session = managed_session.__enter__.return_value
    factory = Mock(return_value=managed_session)

    monkeypatch.setattr(
        session_module,
        "get_session_factory",
        lambda: factory,
    )

    dependency = session_module.get_db_session()

    result = next(dependency)

    assert result is yielded_session

    with pytest.raises(StopIteration):
        next(dependency)

    managed_session.__exit__.assert_called_once()