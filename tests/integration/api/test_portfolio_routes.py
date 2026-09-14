from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from libs.database import get_session_factory
from libs.database.models import (
    PortfolioModel,
    PositionModel,
)
from services.api.main import app

pytestmark = pytest.mark.integration


client = TestClient(app)


USER_HEADERS = {
    "X-User-Id": "api-user-001",
}

OTHER_USER_HEADERS = {
    "X-User-Id": "api-user-002",
}


@pytest.fixture(autouse=True)
def clean_database():
    session_factory = get_session_factory()

    with session_factory() as session:
        session.execute(
            delete(PositionModel)
        )
        session.execute(
            delete(PortfolioModel)
        )
        session.commit()

    yield

    with session_factory() as session:
        session.execute(
            delete(PositionModel)
        )
        session.execute(
            delete(PortfolioModel)
        )
        session.commit()


def create_portfolio() -> dict:
    response = client.post(
        "/api/v1/portfolios",
        headers=USER_HEADERS,
        json={
            "name": "Growth Portfolio",
            "currency": "USD",
        },
    )

    assert response.status_code == 201

    return response.json()


def test_missing_user_header_returns_401() -> None:
    response = client.get(
        "/api/v1/portfolios"
    )

    assert response.status_code == 401


def test_create_portfolio() -> None:
    response = client.post(
        "/api/v1/portfolios",
        headers=USER_HEADERS,
        json={
            "name": "Growth Portfolio",
            "currency": "USD",
        },
    )

    assert response.status_code == 201

    payload = response.json()

    assert payload["user_id"] == "api-user-001"
    assert payload["name"] == "Growth Portfolio"
    assert payload["currency"] == "USD"
    assert payload["positions"] == []


def test_list_portfolios() -> None:
    create_portfolio()

    response = client.get(
        "/api/v1/portfolios",
        headers=USER_HEADERS,
    )

    assert response.status_code == 200

    payload = response.json()

    assert len(payload) == 1
    assert payload[0]["name"] == "Growth Portfolio"


def test_get_portfolio() -> None:
    portfolio = create_portfolio()

    response = client.get(
        (
            "/api/v1/portfolios/"
            f"{portfolio['portfolio_id']}"
        ),
        headers=USER_HEADERS,
    )

    assert response.status_code == 200

    assert (
        response.json()["portfolio_id"]
        == portfolio["portfolio_id"]
    )


def test_other_user_cannot_read_portfolio() -> None:
    portfolio = create_portfolio()

    response = client.get(
        (
            "/api/v1/portfolios/"
            f"{portfolio['portfolio_id']}"
        ),
        headers=OTHER_USER_HEADERS,
    )

    assert response.status_code == 404


def test_add_position() -> None:
    portfolio = create_portfolio()

    response = client.post(
        (
            "/api/v1/portfolios/"
            f"{portfolio['portfolio_id']}"
            "/positions"
        ),
        headers=USER_HEADERS,
        json={
            "symbol": "AAPL",
            "market": "US",
            "quantity": "100",
            "average_cost": "200.50",
        },
    )

    assert response.status_code == 201

    payload = response.json()

    assert payload["symbol"] == "AAPL"
    assert payload["market"] == "US"


def test_duplicate_position_returns_409() -> None:
    portfolio = create_portfolio()

    url = (
        "/api/v1/portfolios/"
        f"{portfolio['portfolio_id']}"
        "/positions"
    )

    body = {
        "symbol": "AAPL",
        "market": "US",
        "quantity": "100",
        "average_cost": "200.50",
    }

    first = client.post(
        url,
        headers=USER_HEADERS,
        json=body,
    )

    second = client.post(
        url,
        headers=USER_HEADERS,
        json=body,
    )

    assert first.status_code == 201
    assert second.status_code == 409


def test_list_positions() -> None:
    portfolio = create_portfolio()

    url = (
        "/api/v1/portfolios/"
        f"{portfolio['portfolio_id']}"
        "/positions"
    )

    client.post(
        url,
        headers=USER_HEADERS,
        json={
            "symbol": "AAPL",
            "market": "US",
            "quantity": "100",
            "average_cost": "200.50",
        },
    )

    response = client.get(
        url,
        headers=USER_HEADERS,
    )

    assert response.status_code == 200

    payload = response.json()

    assert len(payload) == 1
    assert payload[0]["symbol"] == "AAPL"


def test_invalid_position_returns_422() -> None:
    portfolio = create_portfolio()

    response = client.post(
        (
            "/api/v1/portfolios/"
            f"{portfolio['portfolio_id']}"
            "/positions"
        ),
        headers=USER_HEADERS,
        json={
            "symbol": "AAPL",
            "market": "US",
            "quantity": "0",
            "average_cost": "200.50",
        },
    )

    assert response.status_code == 422