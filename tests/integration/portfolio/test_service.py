from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy.orm import Session

from libs.database import get_engine
from libs.database.models import Base
from libs.database.unit_of_work import SqlAlchemyUnitOfWork
from libs.domain.market import Market
from libs.domain.portfolio import Currency
from services.api.portfolio import (
    PortfolioNotFoundError,
    PortfolioService,
    PositionAlreadyExistsError,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def db_session() -> Session:
    """
    Run each test inside an outer transaction.

    PortfolioService is allowed to call commit(), so the Session
    uses a SAVEPOINT. The outer transaction is rolled back after
    each test to keep integration tests isolated.
    """

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
    """
    Build PortfolioService with the production-style
    transaction boundary.

    Integration tests provide the SQLAlchemy Session,
    wrap it in SqlAlchemyUnitOfWork, and inject the
    Unit of Work into PortfolioService.
    """

    unit_of_work = SqlAlchemyUnitOfWork(
        db_session
    )

    return PortfolioService(
        unit_of_work
    )


def test_create_portfolio(
    db_session: Session,
) -> None:
    service = _service(
        db_session
    )

    portfolio = service.create_portfolio(
        user_id="user-001",
        name="Growth Portfolio",
        currency=Currency.USD,
    )

    assert portfolio.user_id == "user-001"
    assert portfolio.name == "Growth Portfolio"
    assert portfolio.currency is Currency.USD
    assert portfolio.positions == ()


def test_create_then_get_portfolio(
    db_session: Session,
) -> None:
    service = _service(
        db_session
    )

    created = service.create_portfolio(
        user_id="user-001",
        name="Growth Portfolio",
    )

    loaded = service.get_portfolio(
        portfolio_id=created.portfolio_id,
    )

    assert (
        loaded.portfolio_id
        == created.portfolio_id
    )

    assert loaded.user_id == "user-001"
    assert loaded.name == "Growth Portfolio"


def test_get_missing_portfolio_raises(
    db_session: Session,
) -> None:
    service = _service(
        db_session
    )

    missing_id = uuid4()

    with pytest.raises(
        PortfolioNotFoundError,
        match="portfolio not found",
    ):
        service.get_portfolio(
            portfolio_id=missing_id,
        )


def test_list_portfolios_filters_by_user(
    db_session: Session,
) -> None:
    service = _service(
        db_session
    )

    first = service.create_portfolio(
        user_id="user-001",
        name="Portfolio One",
    )

    second = service.create_portfolio(
        user_id="user-001",
        name="Portfolio Two",
    )

    service.create_portfolio(
        user_id="user-002",
        name="Other User Portfolio",
    )

    result = service.list_portfolios(
        user_id="user-001",
    )

    ids = {
        portfolio.portfolio_id
        for portfolio in result
    }

    assert len(result) == 2

    assert first.portfolio_id in ids
    assert second.portfolio_id in ids


def test_add_position(
    db_session: Session,
) -> None:
    service = _service(
        db_session
    )

    portfolio = service.create_portfolio(
        user_id="user-001",
        name="Growth Portfolio",
    )

    position = service.add_position(
        portfolio_id=portfolio.portfolio_id,
        symbol="aapl",
        market=Market.US,
        quantity=Decimal("100"),
        average_cost=Decimal("200.50"),
    )

    assert position.symbol == "AAPL"
    assert position.market is Market.US

    assert (
        position.quantity
        == Decimal("100.0000000000")
    )

    assert (
        position.average_cost
        == Decimal("200.5000000000")
    )


def test_add_position_to_missing_portfolio_raises(
    db_session: Session,
) -> None:
    service = _service(
        db_session
    )

    with pytest.raises(
        PortfolioNotFoundError,
        match="portfolio not found",
    ):
        service.add_position(
            portfolio_id=uuid4(),
            symbol="AAPL",
            market=Market.US,
            quantity=Decimal("100"),
            average_cost=Decimal("200"),
        )


def test_duplicate_position_is_rejected(
    db_session: Session,
) -> None:
    service = _service(
        db_session
    )

    portfolio = service.create_portfolio(
        user_id="user-001",
        name="Growth Portfolio",
    )

    service.add_position(
        portfolio_id=portfolio.portfolio_id,
        symbol="AAPL",
        market=Market.US,
        quantity=Decimal("100"),
        average_cost=Decimal("200"),
    )

    with pytest.raises(
        PositionAlreadyExistsError,
        match="position already exists: US:AAPL",
    ):
        service.add_position(
            portfolio_id=portfolio.portfolio_id,
            symbol="aapl",
            market=Market.US,
            quantity=Decimal("50"),
            average_cost=Decimal("220"),
        )


def test_database_unique_violation_is_mapped_to_duplicate_position(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    Verify that the database unique constraint remains the
    final protection against concurrent duplicate inserts.

    The application-level duplicate lookup is intentionally
    bypassed to simulate a race condition where another
    transaction inserts the same business key between the
    duplicate check and INSERT.

    The resulting IntegrityError must be translated into the
    application's PositionAlreadyExistsError, and the failed
    transaction must be rolled back so the Session remains
    usable afterwards.
    """

    service = _service(
        db_session
    )

    portfolio = service.create_portfolio(
        user_id="user-001",
        name="Growth Portfolio",
    )

    service.add_position(
        portfolio_id=portfolio.portfolio_id,
        symbol="AAPL",
        market=Market.US,
        quantity=Decimal("100"),
        average_cost=Decimal("200"),
    )

    # Simulate the application-level duplicate check missing
    # the existing row during a concurrent race.
    monkeypatch.setattr(
        service._uow.portfolios,
        "get_position",
        lambda **_: None,
    )

    with pytest.raises(
        PositionAlreadyExistsError,
        match="position already exists: US:AAPL",
    ):
        service.add_position(
            portfolio_id=portfolio.portfolio_id,
            symbol="aapl",
            market=Market.US,
            quantity=Decimal("50"),
            average_cost=Decimal("220"),
        )

    # The failed INSERT must have been rolled back.
    # A subsequent transaction should still succeed.
    position = service.add_position(
        portfolio_id=portfolio.portfolio_id,
        symbol="MSFT",
        market=Market.US,
        quantity=Decimal("10"),
        average_cost=Decimal("400"),
    )

    assert position.symbol == "MSFT"
    assert position.market is Market.US


def test_list_positions(
    db_session: Session,
) -> None:
    service = _service(
        db_session
    )

    portfolio = service.create_portfolio(
        user_id="user-001",
        name="Growth Portfolio",
    )

    service.add_position(
        portfolio_id=portfolio.portfolio_id,
        symbol="AAPL",
        market=Market.US,
        quantity=Decimal("100"),
        average_cost=Decimal("200"),
    )

    service.add_position(
        portfolio_id=portfolio.portfolio_id,
        symbol="MSFT",
        market=Market.US,
        quantity=Decimal("50"),
        average_cost=Decimal("400"),
    )

    positions = service.list_positions(
        portfolio_id=portfolio.portfolio_id,
    )

    assert len(positions) == 2

    assert {
        position.instrument_key
        for position in positions
    } == {
        "US:AAPL",
        "US:MSFT",
    }


def test_get_portfolio_contains_persisted_positions(
    db_session: Session,
) -> None:
    service = _service(
        db_session
    )

    portfolio = service.create_portfolio(
        user_id="user-001",
        name="Growth Portfolio",
    )

    service.add_position(
        portfolio_id=portfolio.portfolio_id,
        symbol="AAPL",
        market=Market.US,
        quantity=Decimal("100"),
        average_cost=Decimal("200"),
    )

    loaded = service.get_portfolio(
        portfolio_id=portfolio.portfolio_id,
    )

    assert len(loaded.positions) == 1
    assert loaded.positions[0].symbol == "AAPL"

    assert (
        loaded.total_cost_basis
        == Decimal(
            "20000.00000000000000000000"
        )
    )