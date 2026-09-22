from __future__ import annotations

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from libs.database import get_engine
from libs.database.models.watchlist import WatchlistItemModel
from libs.database.repositories.watchlist import WatchlistRepository

pytestmark = pytest.mark.integration


@pytest.fixture
def db_session() -> Session:
    engine = get_engine()

    with Session(engine) as session:
        session.execute(
            delete(
                WatchlistItemModel
            )
        )
        session.commit()

        yield session

        session.rollback()

        session.execute(
            delete(
                WatchlistItemModel
            )
        )
        session.commit()


def test_add_and_get_watchlist_item(
    db_session: Session,
) -> None:
    repository = WatchlistRepository(
        db_session
    )

    created = repository.add(
        user_id="user-001",
        symbol="AAPL",
    )

    db_session.commit()

    loaded = (
        repository
        .get_by_user_and_symbol(
            user_id="user-001",
            symbol="AAPL",
        )
    )

    assert loaded is not None
    assert loaded.id == created.id
    assert loaded.user_id == "user-001"
    assert loaded.symbol == "AAPL"
    assert loaded.created_at is not None


def test_list_for_user_is_user_scoped(
    db_session: Session,
) -> None:
    repository = WatchlistRepository(
        db_session
    )

    repository.add(
        user_id="user-001",
        symbol="AAPL",
    )

    repository.add(
        user_id="user-001",
        symbol="MSFT",
    )

    repository.add(
        user_id="user-002",
        symbol="NVDA",
    )

    db_session.commit()

    result = repository.list_for_user(
        user_id="user-001"
    )

    assert [
        item.symbol
        for item in result
    ] == [
        "AAPL",
        "MSFT",
    ]


def test_count_for_user_is_user_scoped(
    db_session: Session,
) -> None:
    repository = WatchlistRepository(
        db_session
    )

    repository.add(
        user_id="user-001",
        symbol="AAPL",
    )

    repository.add(
        user_id="user-001",
        symbol="MSFT",
    )

    repository.add(
        user_id="user-002",
        symbol="NVDA",
    )

    db_session.commit()

    assert (
        repository.count_for_user(
            user_id="user-001"
        )
        == 2
    )

    assert (
        repository.count_for_user(
            user_id="user-002"
        )
        == 1
    )


def test_get_missing_item_returns_none(
    db_session: Session,
) -> None:
    repository = WatchlistRepository(
        db_session
    )

    result = (
        repository
        .get_by_user_and_symbol(
            user_id="user-001",
            symbol="AAPL",
        )
    )

    assert result is None


def test_delete_existing_item(
    db_session: Session,
) -> None:
    repository = WatchlistRepository(
        db_session
    )

    repository.add(
        user_id="user-001",
        symbol="AAPL",
    )

    db_session.commit()

    deleted = repository.delete(
        user_id="user-001",
        symbol="AAPL",
    )

    db_session.commit()

    assert deleted is True

    assert (
        repository
        .get_by_user_and_symbol(
            user_id="user-001",
            symbol="AAPL",
        )
        is None
    )


def test_delete_missing_item_returns_false(
    db_session: Session,
) -> None:
    repository = WatchlistRepository(
        db_session
    )

    deleted = repository.delete(
        user_id="user-001",
        symbol="AAPL",
    )

    assert deleted is False