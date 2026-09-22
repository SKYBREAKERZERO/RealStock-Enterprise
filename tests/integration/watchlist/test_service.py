from __future__ import annotations

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from libs.database import get_engine
from libs.database.models.watchlist import WatchlistItemModel
from services.api.watchlist import (
    InvalidWatchlistSymbolError,
    WatchlistItemAlreadyExistsError,
    WatchlistItemNotFoundError,
    WatchlistLimitExceededError,
    WatchlistService,
)

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


def test_add_item_normalizes_symbol(
    db_session: Session,
) -> None:
    service = WatchlistService(
        db_session,
        max_items=8,
    )

    item = service.add_item(
        user_id="user-001",
        symbol=" aapl ",
    )

    assert item.user_id == "user-001"
    assert item.symbol == "AAPL"
    assert item.id is not None
    assert item.created_at is not None


def test_list_items_filters_by_user(
    db_session: Session,
) -> None:
    service = WatchlistService(
        db_session,
        max_items=8,
    )

    service.add_item(
        user_id="user-001",
        symbol="AAPL",
    )

    service.add_item(
        user_id="user-001",
        symbol="MSFT",
    )

    service.add_item(
        user_id="user-002",
        symbol="NVDA",
    )

    result = service.list_items(
        user_id="user-001"
    )

    assert [
        item.symbol
        for item in result
    ] == [
        "AAPL",
        "MSFT",
    ]


def test_duplicate_item_is_rejected(
    db_session: Session,
) -> None:
    service = WatchlistService(
        db_session,
        max_items=8,
    )

    service.add_item(
        user_id="user-001",
        symbol="AAPL",
    )

    with pytest.raises(
        WatchlistItemAlreadyExistsError,
        match=(
            "symbol already exists "
            "in watchlist"
        ),
    ):
        service.add_item(
            user_id="user-001",
            symbol="aapl",
        )


def test_same_symbol_is_allowed_for_different_users(
    db_session: Session,
) -> None:
    service = WatchlistService(
        db_session,
        max_items=8,
    )

    first = service.add_item(
        user_id="user-001",
        symbol="AAPL",
    )

    second = service.add_item(
        user_id="user-002",
        symbol="AAPL",
    )

    assert first.user_id == "user-001"
    assert second.user_id == "user-002"

    assert first.id != second.id


def test_invalid_symbol_is_rejected(
    db_session: Session,
) -> None:
    service = WatchlistService(
        db_session,
        max_items=8,
    )

    with pytest.raises(
        InvalidWatchlistSymbolError,
        match="invalid symbol format",
    ):
        service.add_item(
            user_id="user-001",
            symbol="@BAD",
        )


def test_blank_symbol_is_rejected(
    db_session: Session,
) -> None:
    service = WatchlistService(
        db_session,
        max_items=8,
    )

    with pytest.raises(
        InvalidWatchlistSymbolError,
        match="symbol must not be empty",
    ):
        service.add_item(
            user_id="user-001",
            symbol="   ",
        )


def test_watchlist_limit_is_enforced(
    db_session: Session,
) -> None:
    service = WatchlistService(
        db_session,
        max_items=3,
    )

    service.add_item(
        user_id="user-001",
        symbol="AAPL",
    )

    service.add_item(
        user_id="user-001",
        symbol="MSFT",
    )

    service.add_item(
        user_id="user-001",
        symbol="NVDA",
    )

    with pytest.raises(
        WatchlistLimitExceededError,
        match=(
            "watchlist item limit "
            "exceeded"
        ),
    ):
        service.add_item(
            user_id="user-001",
            symbol="GOOGL",
        )


def test_limit_is_scoped_per_user(
    db_session: Session,
) -> None:
    service = WatchlistService(
        db_session,
        max_items=1,
    )

    service.add_item(
        user_id="user-001",
        symbol="AAPL",
    )

    second_user = service.add_item(
        user_id="user-002",
        symbol="MSFT",
    )

    assert second_user.symbol == "MSFT"


def test_delete_item(
    db_session: Session,
) -> None:
    service = WatchlistService(
        db_session,
        max_items=8,
    )

    service.add_item(
        user_id="user-001",
        symbol="AAPL",
    )

    service.delete_item(
        user_id="user-001",
        symbol="aapl",
    )

    result = service.list_items(
        user_id="user-001"
    )

    assert result == []


def test_delete_missing_item_is_rejected(
    db_session: Session,
) -> None:
    service = WatchlistService(
        db_session,
        max_items=8,
    )

    with pytest.raises(
        WatchlistItemNotFoundError,
        match=(
            "watchlist item not found"
        ),
    ):
        service.delete_item(
            user_id="user-001",
            symbol="AAPL",
        )


def test_user_cannot_delete_other_users_item(
    db_session: Session,
) -> None:
    service = WatchlistService(
        db_session,
        max_items=8,
    )

    service.add_item(
        user_id="user-001",
        symbol="AAPL",
    )

    with pytest.raises(
        WatchlistItemNotFoundError,
        match=(
            "watchlist item not found"
        ),
    ):
        service.delete_item(
            user_id="user-002",
            symbol="AAPL",
        )

    original_items = (
        service.list_items(
            user_id="user-001"
        )
    )

    assert [
        item.symbol
        for item in original_items
    ] == [
        "AAPL",
    ]