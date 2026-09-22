from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from libs.database import get_engine
from libs.database.models.watchlist import WatchlistItemModel
from services.api.main import app

pytestmark = pytest.mark.integration


client = TestClient(
    app
)


USER_ONE_HEADERS = {
    "X-User-ID": "user-001",
}


USER_TWO_HEADERS = {
    "X-User-ID": "user-002",
}


@pytest.fixture(
    autouse=True
)
def clean_watchlist() -> None:
    engine = get_engine()

    with Session(engine) as session:
        session.execute(
            delete(
                WatchlistItemModel
            )
        )
        session.commit()

    yield

    with Session(engine) as session:
        session.execute(
            delete(
                WatchlistItemModel
            )
        )
        session.commit()


def test_missing_user_header_returns_401() -> None:
    response = client.get(
        "/api/v1/watchlist"
    )

    assert (
        response.status_code
        == 401
    )

    assert (
        response.json()[
            "detail"
        ]
        == "missing user identity"
    )


def test_empty_watchlist_returns_empty_collection() -> None:
    response = client.get(
        "/api/v1/watchlist",
        headers=USER_ONE_HEADERS,
    )

    assert (
        response.status_code
        == 200
    )

    assert response.json() == {
        "items": [],
        "count": 0,
    }


def test_create_watchlist_item() -> None:
    response = client.post(
        "/api/v1/watchlist",
        headers=USER_ONE_HEADERS,
        json={
            "symbol": " aapl ",
        },
    )

    assert (
        response.status_code
        == 201
    )

    payload = response.json()

    assert (
        payload[
            "symbol"
        ]
        == "AAPL"
    )

    assert (
        payload[
            "watchlist_item_id"
        ]
    )

    assert (
        payload[
            "created_at"
        ]
    )


def test_created_item_is_persisted() -> None:
    create_response = client.post(
        "/api/v1/watchlist",
        headers=USER_ONE_HEADERS,
        json={
            "symbol": "NVDA",
        },
    )

    assert (
        create_response.status_code
        == 201
    )

    list_response = client.get(
        "/api/v1/watchlist",
        headers=USER_ONE_HEADERS,
    )

    assert (
        list_response.status_code
        == 200
    )

    payload = (
        list_response.json()
    )

    assert payload["count"] == 1

    assert (
        payload[
            "items"
        ][0]["symbol"]
        == "NVDA"
    )


def test_duplicate_symbol_returns_409() -> None:
    first = client.post(
        "/api/v1/watchlist",
        headers=USER_ONE_HEADERS,
        json={
            "symbol": "AAPL",
        },
    )

    assert (
        first.status_code
        == 201
    )

    second = client.post(
        "/api/v1/watchlist",
        headers=USER_ONE_HEADERS,
        json={
            "symbol": "aapl",
        },
    )

    assert (
        second.status_code
        == 409
    )

    assert (
        second.json()[
            "detail"
        ]
        == (
            "symbol already exists "
            "in watchlist"
        )
    )


def test_users_have_independent_watchlists() -> None:
    first = client.post(
        "/api/v1/watchlist",
        headers=USER_ONE_HEADERS,
        json={
            "symbol": "AAPL",
        },
    )

    second = client.post(
        "/api/v1/watchlist",
        headers=USER_TWO_HEADERS,
        json={
            "symbol": "MSFT",
        },
    )

    assert (
        first.status_code
        == 201
    )

    assert (
        second.status_code
        == 201
    )

    user_one = client.get(
        "/api/v1/watchlist",
        headers=USER_ONE_HEADERS,
    )

    user_two = client.get(
        "/api/v1/watchlist",
        headers=USER_TWO_HEADERS,
    )

    assert [
        item["symbol"]
        for item
        in user_one.json()[
            "items"
        ]
    ] == [
        "AAPL",
    ]

    assert [
        item["symbol"]
        for item
        in user_two.json()[
            "items"
        ]
    ] == [
        "MSFT",
    ]


def test_same_symbol_allowed_for_different_users() -> None:
    first = client.post(
        "/api/v1/watchlist",
        headers=USER_ONE_HEADERS,
        json={
            "symbol": "AAPL",
        },
    )

    second = client.post(
        "/api/v1/watchlist",
        headers=USER_TWO_HEADERS,
        json={
            "symbol": "AAPL",
        },
    )

    assert (
        first.status_code
        == 201
    )

    assert (
        second.status_code
        == 201
    )


def test_invalid_symbol_returns_422() -> None:
    response = client.post(
        "/api/v1/watchlist",
        headers=USER_ONE_HEADERS,
        json={
            "symbol": "@BAD",
        },
    )

    assert (
        response.status_code
        == 422
    )

    assert (
        response.json()[
            "detail"
        ]
        == "invalid symbol format"
    )


def test_blank_symbol_returns_422() -> None:
    response = client.post(
        "/api/v1/watchlist",
        headers=USER_ONE_HEADERS,
        json={
            "symbol": " ",
        },
    )

    assert (
        response.status_code
        == 422
    )


def test_watchlist_limit_returns_409() -> None:
    symbols = [
        "AAPL",
        "MSFT",
        "GOOGL",
        "AMZN",
        "TSLA",
        "NVDA",
        "AMD",
        "META",
    ]

    for symbol in symbols:
        response = client.post(
            "/api/v1/watchlist",
            headers=USER_ONE_HEADERS,
            json={
                "symbol": symbol,
            },
        )

        assert (
            response.status_code
            == 201
        )

    overflow = client.post(
        "/api/v1/watchlist",
        headers=USER_ONE_HEADERS,
        json={
            "symbol": "NFLX",
        },
    )

    assert (
        overflow.status_code
        == 409
    )

    assert (
        overflow.json()[
            "detail"
        ]
        == (
            "watchlist item "
            "limit exceeded"
        )
    )


def test_delete_watchlist_item() -> None:
    created = client.post(
        "/api/v1/watchlist",
        headers=USER_ONE_HEADERS,
        json={
            "symbol": "AAPL",
        },
    )

    assert (
        created.status_code
        == 201
    )

    deleted = client.delete(
        "/api/v1/watchlist/AAPL",
        headers=USER_ONE_HEADERS,
    )

    assert (
        deleted.status_code
        == 204
    )

    response = client.get(
        "/api/v1/watchlist",
        headers=USER_ONE_HEADERS,
    )

    assert response.json() == {
        "items": [],
        "count": 0,
    }


def test_delete_normalizes_symbol() -> None:
    created = client.post(
        "/api/v1/watchlist",
        headers=USER_ONE_HEADERS,
        json={
            "symbol": "AAPL",
        },
    )

    assert (
        created.status_code
        == 201
    )

    deleted = client.delete(
        "/api/v1/watchlist/aapl",
        headers=USER_ONE_HEADERS,
    )

    assert (
        deleted.status_code
        == 204
    )


def test_delete_missing_item_returns_404() -> None:
    response = client.delete(
        "/api/v1/watchlist/AAPL",
        headers=USER_ONE_HEADERS,
    )

    assert (
        response.status_code
        == 404
    )

    assert (
        response.json()[
            "detail"
        ]
        == "watchlist item not found"
    )


def test_other_user_cannot_delete_item() -> None:
    created = client.post(
        "/api/v1/watchlist",
        headers=USER_ONE_HEADERS,
        json={
            "symbol": "AAPL",
        },
    )

    assert (
        created.status_code
        == 201
    )

    forbidden_delete = (
        client.delete(
            "/api/v1/watchlist/AAPL",
            headers=USER_TWO_HEADERS,
        )
    )

    assert (
        forbidden_delete.status_code
        == 404
    )

    original_user = client.get(
        "/api/v1/watchlist",
        headers=USER_ONE_HEADERS,
    )

    assert (
        original_user.json()[
            "count"
        ]
        == 1
    )