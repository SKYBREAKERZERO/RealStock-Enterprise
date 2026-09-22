from __future__ import annotations

from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from libs.database import get_session_factory
from libs.database.models import PortfolioModel
from services.api.main import app

pytestmark = pytest.mark.integration


client = TestClient(app)


USER_ID = "api-crud-user-001"
OTHER_USER_ID = "api-crud-user-002"


USER_HEADERS = {
    "X-User-ID": USER_ID,
}

OTHER_USER_HEADERS = {
    "X-User-ID": OTHER_USER_ID,
}


def _cleanup_test_users() -> None:
    """
    Delete only data owned by this test module.

    Do not delete all portfolios because the development database
    may contain manually created demo portfolios.
    """

    session_factory = get_session_factory()

    with session_factory() as session:
        session.execute(
            delete(PortfolioModel)
            .where(
                PortfolioModel.user_id.in_(
                    [
                        USER_ID,
                        OTHER_USER_ID,
                    ]
                )
            )
        )

        session.commit()


@pytest.fixture(autouse=True)
def cleanup_test_users():
    """
    Keep API integration tests isolated without destroying
    development/demo portfolio data.
    """

    _cleanup_test_users()

    yield

    _cleanup_test_users()


def _create_portfolio() -> dict:
    response = client.post(
        "/api/v1/portfolios",
        headers=USER_HEADERS,
        json={
            "name": "CRUD Portfolio",
            "currency": "USD",
        },
    )

    assert response.status_code == 201

    return response.json()


def _add_position(
    portfolio_id: str,
) -> dict:
    response = client.post(
        (
            "/api/v1/portfolios/"
            f"{portfolio_id}"
            "/positions"
        ),
        headers=USER_HEADERS,
        json={
            "symbol": "AAPL",
            "market": "US",
            "quantity": "10",
            "average_cost": "200",
        },
    )

    assert response.status_code == 201

    return response.json()


def test_patch_position() -> None:
    portfolio = _create_portfolio()

    position = _add_position(
        portfolio["portfolio_id"]
    )

    response = client.patch(
        (
            "/api/v1/portfolios/"
            f"{portfolio['portfolio_id']}"
            "/positions/"
            f"{position['position_id']}"
        ),
        headers=USER_HEADERS,
        json={
            "quantity": "12",
            "average_cost": "210",
        },
    )

    assert response.status_code == 200

    payload = response.json()

    assert (
        Decimal(
            payload["quantity"]
        )
        == Decimal("12")
    )

    assert (
        Decimal(
            payload["average_cost"]
        )
        == Decimal("210")
    )

    assert (
        Decimal(
            payload["cost_basis"]
        )
        == Decimal("2520")
    )

    assert (
        payload["position_id"]
        == position["position_id"]
    )

    assert (
        payload["symbol"]
        == "AAPL"
    )

    assert (
        payload["market"]
        == "US"
    )


def test_patch_position_rejects_empty_body() -> None:
    portfolio = _create_portfolio()

    position = _add_position(
        portfolio["portfolio_id"]
    )

    response = client.patch(
        (
            "/api/v1/portfolios/"
            f"{portfolio['portfolio_id']}"
            "/positions/"
            f"{position['position_id']}"
        ),
        headers=USER_HEADERS,
        json={},
    )

    assert response.status_code == 422


def test_other_user_cannot_patch_position() -> None:
    portfolio = _create_portfolio()

    position = _add_position(
        portfolio["portfolio_id"]
    )

    response = client.patch(
        (
            "/api/v1/portfolios/"
            f"{portfolio['portfolio_id']}"
            "/positions/"
            f"{position['position_id']}"
        ),
        headers=OTHER_USER_HEADERS,
        json={
            "quantity": "12",
        },
    )

    assert response.status_code == 404


def test_delete_position() -> None:
    portfolio = _create_portfolio()

    position = _add_position(
        portfolio["portfolio_id"]
    )

    response = client.delete(
        (
            "/api/v1/portfolios/"
            f"{portfolio['portfolio_id']}"
            "/positions/"
            f"{position['position_id']}"
        ),
        headers=USER_HEADERS,
    )

    assert response.status_code == 204

    list_response = client.get(
        (
            "/api/v1/portfolios/"
            f"{portfolio['portfolio_id']}"
            "/positions"
        ),
        headers=USER_HEADERS,
    )

    assert list_response.status_code == 200

    assert (
        list_response.json()
        == []
    )


def test_other_user_cannot_delete_position() -> None:
    portfolio = _create_portfolio()

    position = _add_position(
        portfolio["portfolio_id"]
    )

    response = client.delete(
        (
            "/api/v1/portfolios/"
            f"{portfolio['portfolio_id']}"
            "/positions/"
            f"{position['position_id']}"
        ),
        headers=OTHER_USER_HEADERS,
    )

    assert response.status_code == 404