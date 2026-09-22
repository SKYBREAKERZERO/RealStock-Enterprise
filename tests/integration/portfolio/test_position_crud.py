from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from libs.database import get_engine
from libs.database.models import Base
from libs.database.unit_of_work import SqlAlchemyUnitOfWork
from libs.domain.market import Market
from services.api.portfolio import (
    PortfolioService,
    PositionNotFoundError,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def db_session() -> Session:
    engine = get_engine()

    Base.metadata.create_all(
        bind=engine,
    )

    connection = engine.connect()
    transaction = connection.begin()

    session = Session(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    try:
        yield session

    finally:
        session.close()

        if transaction.is_active:
            transaction.rollback()

        connection.close()


def _service(
    db_session: Session,
) -> PortfolioService:
    return PortfolioService(
        SqlAlchemyUnitOfWork(
            db_session
        )
    )


def test_update_position(
    db_session: Session,
) -> None:
    service = _service(
        db_session
    )

    portfolio = service.create_portfolio(
        user_id="crud-user-001",
        name="CRUD Portfolio",
    )

    position = service.add_position(
        portfolio_id=portfolio.portfolio_id,
        symbol="AAPL",
        market=Market.US,
        quantity=Decimal("10"),
        average_cost=Decimal("200"),
    )

    updated = service.update_position(
        portfolio_id=portfolio.portfolio_id,
        position_id=position.position_id,
        quantity=Decimal("12"),
        average_cost=Decimal("210"),
    )

    assert (
        updated.position_id
        == position.position_id
    )

    assert (
        updated.quantity
        == Decimal("12.0000000000")
    )

    assert (
        updated.average_cost
        == Decimal("210.0000000000")
    )

    assert (
        updated.cost_basis
        == Decimal(
            "2520.00000000000000000000"
        )
    )


def test_update_position_can_change_one_field(
    db_session: Session,
) -> None:
    service = _service(
        db_session
    )

    portfolio = service.create_portfolio(
        user_id="crud-user-002",
        name="CRUD Portfolio",
    )

    position = service.add_position(
        portfolio_id=portfolio.portfolio_id,
        symbol="MSFT",
        market=Market.US,
        quantity=Decimal("5"),
        average_cost=Decimal("400"),
    )

    updated = service.update_position(
        portfolio_id=portfolio.portfolio_id,
        position_id=position.position_id,
        quantity=Decimal("7"),
    )

    assert (
        updated.quantity
        == Decimal("7.0000000000")
    )

    assert (
        updated.average_cost
        == Decimal("400.0000000000")
    )


def test_delete_position(
    db_session: Session,
) -> None:
    service = _service(
        db_session
    )

    portfolio = service.create_portfolio(
        user_id="crud-user-003",
        name="CRUD Portfolio",
    )

    position = service.add_position(
        portfolio_id=portfolio.portfolio_id,
        symbol="AAPL",
        market=Market.US,
        quantity=Decimal("10"),
        average_cost=Decimal("200"),
    )

    service.delete_position(
        portfolio_id=portfolio.portfolio_id,
        position_id=position.position_id,
    )

    positions = service.list_positions(
        portfolio_id=portfolio.portfolio_id,
    )

    assert positions == []


def test_missing_position_is_404_domain_error(
    db_session: Session,
) -> None:
    service = _service(
        db_session
    )

    portfolio = service.create_portfolio(
        user_id="crud-user-004",
        name="CRUD Portfolio",
    )

    with pytest.raises(
        PositionNotFoundError,
        match="position not found",
    ):
        service.delete_position(
            portfolio_id=portfolio.portfolio_id,
            position_id=uuid4(),
        )
