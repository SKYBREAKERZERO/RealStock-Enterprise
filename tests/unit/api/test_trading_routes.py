from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from libs.trading.enums import (
    OrderSide,
    OrderStatus,
    OrderType,
)
from libs.trading.execution import Execution
from libs.trading.models import (
    PaperAccount,
    PaperOrder,
    Position,
)
from services.api.dependencies import (
    get_trading_portfolio_service,
    get_trading_query_service,
)
from services.api.routes.trading import router
from services.trading.trading_portfolio_service import (
    TradingPortfolioAccountNotFoundError,
    TradingPortfolioSnapshot,
    TradingPortfolioValuationUnavailableError,
    TradingPositionValuation,
)

USER_HEADERS = {
    "X-User-Id": "user-001",
}


def build_client(
    query_service: Mock,
    *,
    portfolio_service: Mock | None = None,
) -> TestClient:
    app = FastAPI()

    app.include_router(
        router
    )

    app.dependency_overrides[
        get_trading_query_service
    ] = lambda: query_service

    if portfolio_service is not None:
        app.dependency_overrides[
            get_trading_portfolio_service
        ] = lambda: portfolio_service

    return TestClient(
        app
    )


def test_get_account_returns_account() -> None:
    account = PaperAccount(
        initial_cash=Decimal("100000"),
    )

    account.cash_balance = Decimal("97500")

    service = Mock()
    service.get_account.return_value = account

    client = build_client(
        service
    )

    response = client.get(
        "/api/v1/trading/account",
        headers=USER_HEADERS,
    )

    assert response.status_code == 200

    assert response.json() == {
        "account_id": str(
            account.account_id
        ),
        "initial_cash": "100000",
        "cash_balance": "97500",
    }

    service.get_account.assert_called_once_with(
        user_id="user-001",
    )


def test_get_account_returns_404_when_missing() -> None:
    service = Mock()
    service.get_account.return_value = None

    client = build_client(
        service
    )

    response = client.get(
        "/api/v1/trading/account",
        headers=USER_HEADERS,
    )

    assert response.status_code == 404

    assert response.json() == {
        "detail": "paper account not found",
    }


def test_get_portfolio_returns_snapshot() -> None:
    account_id = uuid4()

    snapshot = TradingPortfolioSnapshot(
        account_id=account_id,
        initial_cash=Decimal("100000"),
        cash_balance=Decimal("95950"),
        total_cost_basis=Decimal("4050"),
        market_value=Decimal("4200"),
        equity=Decimal("100150"),
        realized_pnl=Decimal("25"),
        unrealized_pnl=Decimal("150"),
        positions=(
            TradingPositionValuation(
                symbol="AAPL",
                quantity=10,
                average_cost=Decimal("200"),
                mark_price=Decimal("210"),
                cost_basis=Decimal("2000"),
                market_value=Decimal("2100"),
                realized_pnl=Decimal("25"),
                unrealized_pnl=Decimal("100"),
            ),
        ),
    )

    query_service = Mock()
    portfolio_service = Mock()
    portfolio_service.get_snapshot.return_value = (
        snapshot
    )

    client = build_client(
        query_service,
        portfolio_service=portfolio_service,
    )

    response = client.get(
        "/api/v1/trading/portfolio",
        headers=USER_HEADERS,
    )

    assert response.status_code == 200

    assert response.json() == {
        "account_id": str(
            account_id
        ),
        "initial_cash": "100000",
        "cash_balance": "95950",
        "total_cost_basis": "4050",
        "market_value": "4200",
        "equity": "100150",
        "realized_pnl": "25",
        "unrealized_pnl": "150",
        "total_pnl": "175",
        "positions": [
            {
                "symbol": "AAPL",
                "quantity": 10,
                "average_cost": "200",
                "mark_price": "210",
                "cost_basis": "2000",
                "market_value": "2100",
                "realized_pnl": "25",
                "unrealized_pnl": "100",
                "total_pnl": "125",
            }
        ],
    }

    (
        portfolio_service
        .get_snapshot
        .assert_called_once_with(
            user_id="user-001",
        )
    )


def test_get_portfolio_returns_404_when_account_missing() -> None:
    query_service = Mock()
    portfolio_service = Mock()

    portfolio_service.get_snapshot.side_effect = (
        TradingPortfolioAccountNotFoundError(
            "Paper account not found."
        )
    )

    client = build_client(
        query_service,
        portfolio_service=portfolio_service,
    )

    response = client.get(
        "/api/v1/trading/portfolio",
        headers=USER_HEADERS,
    )

    assert response.status_code == 404

    assert response.json() == {
        "detail": "paper account not found",
    }


def test_get_portfolio_returns_503_when_price_missing() -> None:
    query_service = Mock()
    portfolio_service = Mock()

    portfolio_service.get_snapshot.side_effect = (
        TradingPortfolioValuationUnavailableError(
            "Missing market price for AAPL."
        )
    )

    client = build_client(
        query_service,
        portfolio_service=portfolio_service,
    )

    response = client.get(
        "/api/v1/trading/portfolio",
        headers=USER_HEADERS,
    )

    assert response.status_code == 503

    assert response.json() == {
        "detail": (
            "paper portfolio valuation "
            "is unavailable"
        ),
    }


def test_list_positions_returns_positions() -> None:
    service = Mock()

    service.list_positions.return_value = [
        Position(
            symbol="AAPL",
            quantity=10,
            average_cost=Decimal("200"),
            realized_pnl=Decimal("25"),
        )
    ]

    client = build_client(
        service
    )

    response = client.get(
        "/api/v1/trading/positions",
        headers=USER_HEADERS,
    )

    assert response.status_code == 200

    assert response.json() == [
        {
            "symbol": "AAPL",
            "quantity": 10,
            "average_cost": "200",
            "realized_pnl": "25",
        }
    ]


def test_list_orders_forwards_limit() -> None:
    account_id = uuid4()

    order = PaperOrder(
        account_id=account_id,
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=10,
        order_type=OrderType.LIMIT,
        status=OrderStatus.PENDING,
        filled_quantity=0,
        limit_price=Decimal("200"),
    )

    service = Mock()
    service.list_orders.return_value = [
        order
    ]

    client = build_client(
        service
    )

    response = client.get(
        "/api/v1/trading/orders?limit=25",
        headers=USER_HEADERS,
    )

    assert response.status_code == 200

    payload = response.json()

    assert len(payload) == 1
    assert payload[0]["order_id"] == str(
        order.order_id
    )
    assert payload[0]["side"] == "BUY"
    assert payload[0]["order_type"] == "LIMIT"
    assert payload[0]["status"] == "PENDING"
    assert payload[0]["limit_price"] == "200"

    service.list_orders.assert_called_once_with(
        user_id="user-001",
        limit=25,
    )


def test_list_open_orders_returns_open_orders() -> None:
    account_id = uuid4()

    order = PaperOrder(
        account_id=account_id,
        symbol="MSFT",
        side=OrderSide.SELL,
        quantity=5,
        order_type=OrderType.LIMIT,
        status=OrderStatus.PENDING,
        filled_quantity=0,
        limit_price=Decimal("450"),
    )

    service = Mock()
    service.list_open_orders.return_value = [
        order
    ]

    client = build_client(
        service
    )

    response = client.get(
        "/api/v1/trading/orders/open?limit=50",
        headers=USER_HEADERS,
    )

    assert response.status_code == 200

    assert response.json()[0]["symbol"] == "MSFT"

    (
        service.list_open_orders
        .assert_called_once_with(
            user_id="user-001",
            limit=50,
        )
    )


def test_list_executions_returns_execution_history() -> None:
    execution = Execution(
        order_id=uuid4(),
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=10,
        price=Decimal("199"),
    )

    service = Mock()
    service.list_executions.return_value = [
        execution
    ]

    client = build_client(
        service
    )

    response = client.get(
        "/api/v1/trading/executions?limit=10",
        headers=USER_HEADERS,
    )

    assert response.status_code == 200

    assert response.json() == [
        {
            "execution_id": str(
                execution.execution_id
            ),
            "order_id": str(
                execution.order_id
            ),
            "symbol": "AAPL",
            "side": "BUY",
            "quantity": 10,
            "price": "199",
        }
    ]

    service.list_executions.assert_called_once_with(
        user_id="user-001",
        limit=10,
    )


def test_account_scoped_query_returns_404_when_missing() -> None:
    service = Mock()
    service.list_positions.side_effect = ValueError(
        "Paper account for user 'user-001' not found."
    )

    client = build_client(
        service
    )

    response = client.get(
        "/api/v1/trading/positions",
        headers=USER_HEADERS,
    )

    assert response.status_code == 404

    assert response.json() == {
        "detail": "paper account not found",
    }


def test_missing_user_header_returns_401() -> None:
    service = Mock()

    client = build_client(
        service
    )

    response = client.get(
        "/api/v1/trading/account"
    )

    assert response.status_code == 401

    assert response.json() == {
        "detail": "missing X-User-Id header",
    }

    service.get_account.assert_not_called()


def test_invalid_limit_returns_422() -> None:
    service = Mock()

    client = build_client(
        service
    )

    response = client.get(
        "/api/v1/trading/orders?limit=501",
        headers=USER_HEADERS,
    )

    assert response.status_code == 422

    service.list_orders.assert_not_called()
