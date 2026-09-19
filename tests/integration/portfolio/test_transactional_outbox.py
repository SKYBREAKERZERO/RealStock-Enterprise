from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from libs.database import get_engine
from libs.database.models.outbox import OutboxEventModel
from libs.database.models.portfolio import (
    PortfolioModel,
    PositionModel,
)
from libs.database.unit_of_work import (
    SqlAlchemyUnitOfWork,
)
from libs.domain.market import Market
from libs.events.portfolio import (
    PORTFOLIO_CREATED,
    PORTFOLIO_EVENT_SCHEMA_VERSION,
    PORTFOLIO_POSITION_ADDED,
)
from services.api.portfolio import PortfolioService

pytestmark = pytest.mark.integration


@pytest.fixture
def db_session() -> Session:
    """
    Run each test against the Alembic-managed database schema.

    PortfolioService is allowed to call commit(), so the Session
    joins the outer transaction using SAVEPOINT semantics.

    The outer transaction is rolled back after each test to keep
    integration tests isolated.

    Schema creation is intentionally NOT performed here.
    Alembic is the authoritative schema-management mechanism.
    """

    engine = get_engine()

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
    Build PortfolioService using the production-style
    SQLAlchemy Unit of Work.
    """

    return PortfolioService(
        SqlAlchemyUnitOfWork(
            db_session
        )
    )


def _outbox_count(
    db_session: Session,
) -> int:
    """
    Return the total number of transactional outbox rows
    visible in the current test transaction.
    """

    statement = (
        select(func.count())
        .select_from(
            OutboxEventModel
        )
    )

    return (
        db_session
        .execute(statement)
        .scalar_one()
    )


def test_create_portfolio_persists_outbox_event_atomically(
    db_session: Session,
) -> None:
    """
    Creating a portfolio must persist both:

    - the portfolio business row
    - the portfolio.created outbox event

    through the same transaction boundary.
    """

    service = _service(
        db_session
    )

    portfolio = service.create_portfolio(
        user_id="outbox-user-001",
        name="Growth Portfolio",
    )

    portfolio_model = (
        db_session
        .execute(
            select(
                PortfolioModel
            ).where(
                PortfolioModel.id
                == portfolio.portfolio_id
            )
        )
        .scalar_one()
    )

    outbox_event = (
        db_session
        .execute(
            select(
                OutboxEventModel
            ).where(
                OutboxEventModel.aggregate_type
                == "portfolio",
                OutboxEventModel.aggregate_id
                == str(
                    portfolio.portfolio_id
                ),
                OutboxEventModel.event_type
                == PORTFOLIO_CREATED,
            )
        )
        .scalar_one()
    )

    assert (
        portfolio_model.id
        == portfolio.portfolio_id
    )

    assert (
        portfolio_model.user_id
        == portfolio.user_id
    )

    assert (
        outbox_event.aggregate_type
        == "portfolio"
    )

    assert (
        outbox_event.aggregate_id
        == str(
            portfolio.portfolio_id
        )
    )

    assert (
        outbox_event.event_type
        == PORTFOLIO_CREATED
    )

    assert (
        outbox_event.schema_version
        == PORTFOLIO_EVENT_SCHEMA_VERSION
    )

    assert (
        outbox_event.payload[
            "portfolio_id"
        ]
        == str(
            portfolio.portfolio_id
        )
    )

    assert (
        outbox_event.payload[
            "user_id"
        ]
        == portfolio.user_id
    )

    assert (
        outbox_event.payload[
            "name"
        ]
        == portfolio.name
    )

    assert (
        outbox_event.payload[
            "currency"
        ]
        == portfolio.currency.value
    )

    assert outbox_event.published_at is None
    assert outbox_event.attempt_count == 0
    assert outbox_event.last_error is None


def test_create_portfolio_rolls_back_when_outbox_write_fails(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    If the outbox write fails after the portfolio INSERT has
    already been flushed, the entire transaction must roll back.

    A portfolio row must not remain without its corresponding
    integration event.
    """

    service = _service(
        db_session
    )

    outbox_count_before = (
        _outbox_count(
            db_session
        )
    )

    def fail_outbox_write(
        **_: object,
    ) -> None:
        raise RuntimeError(
            "simulated outbox failure"
        )

    monkeypatch.setattr(
        service._uow.outbox,
        "add_event",
        fail_outbox_write,
    )

    with pytest.raises(
        RuntimeError,
        match="simulated outbox failure",
    ):
        service.create_portfolio(
            user_id="rollback-user-001",
            name="Must Roll Back",
        )

    portfolio_model = (
        db_session
        .execute(
            select(
                PortfolioModel
            ).where(
                PortfolioModel.user_id
                == "rollback-user-001"
            )
        )
        .scalar_one_or_none()
    )

    assert portfolio_model is None

    assert (
        _outbox_count(
            db_session
        )
        == outbox_count_before
    )


def test_add_position_persists_outbox_event_atomically(
    db_session: Session,
) -> None:
    """
    Adding a position must persist both:

    - the position business row
    - the portfolio.position.added outbox event

    through the same transaction boundary.
    """

    service = _service(
        db_session
    )

    portfolio = service.create_portfolio(
        user_id="outbox-user-002",
        name="Position Portfolio",
    )

    position = service.add_position(
        portfolio_id=(
            portfolio.portfolio_id
        ),
        symbol="AAPL",
        market=Market.US,
        quantity=Decimal("100"),
        average_cost=Decimal(
            "200.50"
        ),
    )

    position_model = (
        db_session
        .execute(
            select(
                PositionModel
            ).where(
                PositionModel.id
                == position.position_id
            )
        )
        .scalar_one()
    )

    outbox_event = (
        db_session
        .execute(
            select(
                OutboxEventModel
            ).where(
                OutboxEventModel.aggregate_type
                == "portfolio",
                OutboxEventModel.aggregate_id
                == str(
                    portfolio.portfolio_id
                ),
                OutboxEventModel.event_type
                == PORTFOLIO_POSITION_ADDED,
            )
        )
        .scalar_one()
    )

    assert (
        position_model.id
        == position.position_id
    )

    assert (
        position_model.portfolio_id
        == portfolio.portfolio_id
    )

    assert position_model.symbol == "AAPL"

    assert (
        position_model.market
        == Market.US.value
    )

    assert (
        outbox_event.aggregate_type
        == "portfolio"
    )

    assert (
        outbox_event.aggregate_id
        == str(
            portfolio.portfolio_id
        )
    )

    assert (
        outbox_event.event_type
        == PORTFOLIO_POSITION_ADDED
    )

    assert (
        outbox_event.schema_version
        == PORTFOLIO_EVENT_SCHEMA_VERSION
    )

    assert (
        outbox_event.payload[
            "portfolio_id"
        ]
        == str(
            portfolio.portfolio_id
        )
    )

    assert (
        outbox_event.payload[
            "position_id"
        ]
        == str(
            position.position_id
        )
    )

    assert (
        outbox_event.payload[
            "symbol"
        ]
        == position.symbol
    )

    assert (
        outbox_event.payload[
            "market"
        ]
        == position.market.value
    )

    assert (
        outbox_event.payload[
            "quantity"
        ]
        == str(
            position.quantity
        )
    )

    assert (
        outbox_event.payload[
            "average_cost"
        ]
        == str(
            position.average_cost
        )
    )

    assert outbox_event.published_at is None
    assert outbox_event.attempt_count == 0
    assert outbox_event.last_error is None


def test_add_position_rolls_back_when_outbox_write_fails(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    If the outbox write fails after the position INSERT has
    already been flushed, the position must also roll back.

    This proves that the business write and integration-event
    write participate in one atomic transaction.
    """

    service = _service(
        db_session
    )

    portfolio = service.create_portfolio(
        user_id="rollback-user-002",
        name="Position Rollback",
    )

    outbox_count_before = (
        _outbox_count(
            db_session
        )
    )

    def fail_outbox_write(
        **_: object,
    ) -> None:
        raise RuntimeError(
            "simulated outbox failure"
        )

    monkeypatch.setattr(
        service._uow.outbox,
        "add_event",
        fail_outbox_write,
    )

    with pytest.raises(
        RuntimeError,
        match="simulated outbox failure",
    ):
        service.add_position(
            portfolio_id=(
                portfolio.portfolio_id
            ),
            symbol="MSFT",
            market=Market.US,
            quantity=Decimal("10"),
            average_cost=Decimal(
                "400"
            ),
        )

    positions = (
        db_session
        .execute(
            select(
                PositionModel
            ).where(
                PositionModel.portfolio_id
                == portfolio.portfolio_id
            )
        )
        .scalars()
        .all()
    )

    assert positions == []

    assert (
        _outbox_count(
            db_session
        )
        == outbox_count_before
    )