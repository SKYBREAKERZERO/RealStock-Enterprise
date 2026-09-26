from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session

from libs.database.models import (
    PaperAccountModel,
    PaperExecutionModel,
    PaperOrderModel,
    PaperPositionModel,
)
from libs.database.repositories.trading import (
    PaperAccountRepository,
    PaperExecutionRepository,
    PaperOrderRepository,
    PaperPositionRepository,
)
from libs.database.session import get_session_factory
from libs.database.unit_of_work import SqlAlchemyUnitOfWork
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
)
from services.api.main import app
from services.trading.trading_portfolio_service import (
    TradingPortfolioService,
)

USER_ID = "integration-trader"
OTHER_USER_ID = "integration-other-user"

USER_HEADERS = {
    "X-User-Id": USER_ID,
}

OTHER_USER_HEADERS = {
    "X-User-Id": OTHER_USER_ID,
}


class StaticTradingPriceSource:
    def __init__(
        self,
        prices: dict[str, Decimal],
    ) -> None:
        self._prices = prices

    def get_prices(
        self,
        symbols: list[str],
    ) -> dict[str, Decimal]:
        return {
            symbol: self._prices[symbol]
            for symbol in symbols
            if symbol in self._prices
        }


def _cleanup_trading_tables() -> None:
    session_factory = get_session_factory()

    with session_factory() as session:
        session.execute(
            delete(PaperExecutionModel)
        )
        session.execute(
            delete(PaperOrderModel)
        )
        session.execute(
            delete(PaperPositionModel)
        )
        session.execute(
            delete(PaperAccountModel)
        )
        session.commit()


@pytest.fixture(autouse=True)
def clean_trading_tables() -> Iterator[None]:
    _cleanup_trading_tables()

    try:
        yield

    finally:
        app.dependency_overrides.pop(
            get_trading_portfolio_service,
            None,
        )
        _cleanup_trading_tables()


@pytest.fixture
def session() -> Iterator[Session]:
    session_factory = get_session_factory()
    db_session = session_factory()

    try:
        yield db_session

    finally:
        if db_session.in_transaction():
            db_session.rollback()

        db_session.close()


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


def _seed_account_state(
    session: Session,
    *,
    user_id: str = USER_ID,
) -> PaperAccount:
    account = PaperAccount(
        initial_cash=Decimal("100000"),
        cash_balance=Decimal("97930"),
    )

    if account.account_id is None:
        raise RuntimeError(
            "Paper account must have an account_id."
        )

    account_repository = PaperAccountRepository(
        session
    )

    account_repository.add(
        user_id=user_id,
        account=account,
    )

    position_repository = PaperPositionRepository(
        session
    )

    position_repository.upsert(
        account_id=account.account_id,
        position=Position(
            symbol="AAPL",
            quantity=10,
            average_cost=Decimal("212"),
            realized_pnl=Decimal("0"),
        ),
    )

    position_repository.upsert(
        account_id=account.account_id,
        position=Position(
            symbol="MSFT",
            quantity=0,
            average_cost=Decimal("0"),
            realized_pnl=Decimal("50"),
        ),
    )

    order_repository = PaperOrderRepository(
        session
    )

    filled_order = PaperOrder(
        account_id=account.account_id,
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=10,
        order_type=OrderType.MARKET,
        status=OrderStatus.FILLED,
        filled_quantity=10,
    )

    order_repository.add(
        filled_order
    )

    pending_order = PaperOrder(
        account_id=account.account_id,
        symbol="MSFT",
        side=OrderSide.BUY,
        quantity=5,
        order_type=OrderType.LIMIT,
        status=OrderStatus.PENDING,
        filled_quantity=0,
        limit_price=Decimal("400"),
    )

    order_repository.add(
        pending_order
    )

    execution_repository = (
        PaperExecutionRepository(
            session
        )
    )

    execution_repository.add(
        account_id=account.account_id,
        execution=Execution(
            order_id=filled_order.order_id,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=10,
            price=Decimal("212"),
        ),
    )

    session.commit()

    return account


def _override_portfolio_service() -> Iterator[
    TradingPortfolioService
]:
    session_factory = get_session_factory()

    with session_factory() as db_session:
        yield TradingPortfolioService(
            unit_of_work=SqlAlchemyUnitOfWork(
                db_session
            ),
            price_source=StaticTradingPriceSource(
                {
                    "AAPL": Decimal("220"),
                }
            ),
        )


def test_account_endpoint_reads_real_postgresql(
    session: Session,
    client: TestClient,
) -> None:
    account = _seed_account_state(
        session
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
        "initial_cash": "100000.000000",
        "cash_balance": "97930.000000",
    }


def test_positions_endpoint_reads_real_postgresql(
    session: Session,
    client: TestClient,
) -> None:
    _seed_account_state(
        session
    )

    response = client.get(
        "/api/v1/trading/positions",
        headers=USER_HEADERS,
    )

    assert response.status_code == 200

    payload = response.json()

    assert [
        item["symbol"]
        for item in payload
    ] == [
        "AAPL",
        "MSFT",
    ]

    assert payload[0] == {
        "symbol": "AAPL",
        "quantity": 10,
        "average_cost": "212.000000",
        "realized_pnl": "0.000000",
    }

    assert payload[1] == {
        "symbol": "MSFT",
        "quantity": 0,
        "average_cost": "0.000000",
        "realized_pnl": "50.000000",
    }


def test_orders_and_open_orders_read_real_postgresql(
    session: Session,
    client: TestClient,
) -> None:
    _seed_account_state(
        session
    )

    orders_response = client.get(
        "/api/v1/trading/orders?limit=20",
        headers=USER_HEADERS,
    )

    assert orders_response.status_code == 200

    orders = orders_response.json()

    assert len(orders) == 2

    by_status = {
        item["status"]: item
        for item in orders
    }

    assert by_status["FILLED"]["symbol"] == "AAPL"
    assert (
        by_status["FILLED"]["filled_quantity"]
        == 10
    )
    assert (
        by_status["FILLED"]["order_type"]
        == "MARKET"
    )

    assert by_status["PENDING"]["symbol"] == "MSFT"
    assert (
        by_status["PENDING"]["limit_price"]
        == "400.000000"
    )

    open_response = client.get(
        "/api/v1/trading/orders/open?limit=20",
        headers=USER_HEADERS,
    )

    assert open_response.status_code == 200

    open_orders = open_response.json()

    assert len(open_orders) == 1
    assert open_orders[0]["status"] == "PENDING"
    assert open_orders[0]["symbol"] == "MSFT"


def test_executions_endpoint_reads_real_postgresql(
    session: Session,
    client: TestClient,
) -> None:
    _seed_account_state(
        session
    )

    response = client.get(
        "/api/v1/trading/executions?limit=20",
        headers=USER_HEADERS,
    )

    assert response.status_code == 200

    payload = response.json()

    assert len(payload) == 1

    assert payload[0]["symbol"] == "AAPL"
    assert payload[0]["side"] == "BUY"
    assert payload[0]["quantity"] == 10
    assert payload[0]["price"] == "212.000000"


def test_portfolio_endpoint_values_real_postgresql_state(
    session: Session,
    client: TestClient,
) -> None:
    account = _seed_account_state(
        session
    )

    app.dependency_overrides[
        get_trading_portfolio_service
    ] = _override_portfolio_service

    response = client.get(
        "/api/v1/trading/portfolio",
        headers=USER_HEADERS,
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["account_id"] == str(
        account.account_id
    )
    assert payload["initial_cash"] == "100000.000000"
    assert payload["cash_balance"] == "97930.000000"

    assert payload["total_cost_basis"] == "2120.000000"
    assert payload["market_value"] == "2200"
    assert payload["equity"] == "100130.000000"

    assert payload["realized_pnl"] == "50.000000"
    assert payload["unrealized_pnl"] == "80.000000"
    assert payload["total_pnl"] == "130.000000"

    positions = {
        item["symbol"]: item
        for item in payload["positions"]
    }

    assert positions["AAPL"] == {
        "symbol": "AAPL",
        "quantity": 10,
        "average_cost": "212.000000",
        "mark_price": "220",
        "cost_basis": "2120.000000",
        "market_value": "2200",
        "realized_pnl": "0.000000",
        "unrealized_pnl": "80.000000",
        "total_pnl": "80.000000",
    }

    assert positions["MSFT"] == {
        "symbol": "MSFT",
        "quantity": 0,
        "average_cost": "0.000000",
        "mark_price": None,
        "cost_basis": "0",
        "market_value": "0",
        "realized_pnl": "50.000000",
        "unrealized_pnl": "0",
        "total_pnl": "50.000000",
    }


def test_other_user_cannot_read_account_state(
    session: Session,
    client: TestClient,
) -> None:
    _seed_account_state(
        session
    )

    account_response = client.get(
        "/api/v1/trading/account",
        headers=OTHER_USER_HEADERS,
    )

    assert account_response.status_code == 404

    assert account_response.json() == {
        "detail": "paper account not found",
    }

    positions_response = client.get(
        "/api/v1/trading/positions",
        headers=OTHER_USER_HEADERS,
    )

    assert positions_response.status_code == 404

    assert positions_response.json() == {
        "detail": "paper account not found",
    }


def test_missing_account_returns_404_from_real_stack(
    client: TestClient,
) -> None:
    response = client.get(
        "/api/v1/trading/account",
        headers=USER_HEADERS,
    )

    assert response.status_code == 404

    assert response.json() == {
        "detail": "paper account not found",
    }
