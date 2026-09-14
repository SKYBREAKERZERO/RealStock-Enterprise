from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy.orm import Session

from libs.database import get_engine
from libs.database.models import Base
from libs.database.repositories import (
    PortfolioRepository,
)
from libs.domain.market import Market
from libs.domain.portfolio import (
    Currency,
    Portfolio,
    Position,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def db_session() -> Session:
    engine = get_engine()

    Base.metadata.create_all(
        bind=engine,
    )

    connection = engine.connect()

    transaction = (
        connection.begin()
    )

    session = Session(
        bind=connection,
        expire_on_commit=False,
    )

    try:
        yield session

    finally:
        session.close()

        transaction.rollback()

        connection.close()


def test_create_and_get_portfolio(
    db_session: Session,
) -> None:
    repository = PortfolioRepository(
        db_session
    )

    portfolio = Portfolio(
        user_id="user-001",
        name="Growth Portfolio",
        currency=Currency.USD,
    )

    created = (
        repository.create_portfolio(
            portfolio
        )
    )

    loaded = repository.get_portfolio(
        portfolio.portfolio_id
    )

    assert created.portfolio_id == portfolio.portfolio_id

    assert loaded is not None

    assert (
        loaded.portfolio_id
        == portfolio.portfolio_id
    )

    assert loaded.user_id == "user-001"

    assert (
        loaded.name
        == "Growth Portfolio"
    )

    assert loaded.currency is Currency.USD


def test_get_missing_portfolio_returns_none(
    db_session: Session,
) -> None:
    from uuid import uuid4

    repository = PortfolioRepository(
        db_session
    )

    result = repository.get_portfolio(
        uuid4()
    )

    assert result is None


def test_list_portfolios_by_user(
    db_session: Session,
) -> None:
    repository = PortfolioRepository(
        db_session
    )

    first = Portfolio(
        user_id="user-001",
        name="Portfolio One",
    )

    second = Portfolio(
        user_id="user-001",
        name="Portfolio Two",
    )

    other_user = Portfolio(
        user_id="user-002",
        name="Other Portfolio",
    )

    repository.create_portfolio(
        first
    )

    repository.create_portfolio(
        second
    )

    repository.create_portfolio(
        other_user
    )

    result = repository.list_portfolios(
        user_id="user-001",
    )

    assert len(result) == 2

    ids = {
        portfolio.portfolio_id
        for portfolio in result
    }

    assert first.portfolio_id in ids
    assert second.portfolio_id in ids
    assert other_user.portfolio_id not in ids


def test_add_and_get_position(
    db_session: Session,
) -> None:
    repository = PortfolioRepository(
        db_session
    )

    portfolio = Portfolio(
        user_id="user-001",
        name="Growth Portfolio",
    )

    repository.create_portfolio(
        portfolio
    )

    position = Position(
        symbol="aapl",
        market=Market.US,
        quantity=Decimal("100"),
        average_cost=Decimal("200.50"),
    )

    created = repository.add_position(
        portfolio_id=(
            portfolio.portfolio_id
        ),
        position=position,
    )

    loaded = repository.get_position(
        portfolio_id=(
            portfolio.portfolio_id
        ),
        market=Market.US,
        symbol="aapl",
    )

    assert created.symbol == "AAPL"

    assert loaded is not None

    assert loaded.symbol == "AAPL"

    assert (
        loaded.quantity
        == Decimal("100.0000000000")
    )

    assert (
        loaded.average_cost
        == Decimal("200.5000000000")
    )


def test_list_positions(
    db_session: Session,
) -> None:
    repository = PortfolioRepository(
        db_session
    )

    portfolio = Portfolio(
        user_id="user-001",
        name="Growth Portfolio",
    )

    repository.create_portfolio(
        portfolio
    )

    repository.add_position(
        portfolio_id=(
            portfolio.portfolio_id
        ),
        position=Position(
            symbol="MSFT",
            market=Market.US,
            quantity=Decimal("20"),
            average_cost=Decimal("400"),
        ),
    )

    repository.add_position(
        portfolio_id=(
            portfolio.portfolio_id
        ),
        position=Position(
            symbol="AAPL",
            market=Market.US,
            quantity=Decimal("100"),
            average_cost=Decimal("200"),
        ),
    )

    result = repository.list_positions(
        portfolio_id=(
            portfolio.portfolio_id
        )
    )

    assert len(result) == 2

    assert (
        result[0].instrument_key
        == "US:AAPL"
    )

    assert (
        result[1].instrument_key
        == "US:MSFT"
    )


def test_get_portfolio_includes_positions(
    db_session: Session,
) -> None:
    repository = PortfolioRepository(
        db_session
    )

    portfolio = Portfolio(
        user_id="user-001",
        name="Growth Portfolio",
    )

    repository.create_portfolio(
        portfolio
    )

    repository.add_position(
        portfolio_id=(
            portfolio.portfolio_id
        ),
        position=Position(
            symbol="AAPL",
            market=Market.US,
            quantity=Decimal("100"),
            average_cost=Decimal("200"),
        ),
    )

    loaded = repository.get_portfolio(
        portfolio.portfolio_id
    )

    assert loaded is not None

    assert len(loaded.positions) == 1

    assert (
        loaded.positions[0].symbol
        == "AAPL"
    )

    assert (
        loaded.total_cost_basis
        == Decimal(
            "20000.00000000000000000000"
        )
    )