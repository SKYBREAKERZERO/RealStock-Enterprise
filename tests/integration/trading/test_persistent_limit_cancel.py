from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from libs.database.models import (
    PaperAccountModel,
    PaperExecutionModel,
    PaperOrderModel,
    PaperPositionModel,
)
from libs.database.repositories.trading import (
    PaperAccountRepository,
    PaperOrderRepository,
    PaperPositionRepository,
)
from libs.database.session import get_session_factory
from libs.database.unit_of_work import SqlAlchemyUnitOfWork
from libs.trading.enums import (
    OrderStatus,
)
from libs.trading.paper_broker import PaperBroker
from services.trading.paper_trading_service import (
    PaperTradingService,
)
from services.trading.persistent_paper_trading_service import (
    PersistentPaperTradingService,
)
from services.trading.quote_service import (
    QuoteService,
    RawQuote,
    StaticQuoteProvider,
)

pytestmark = pytest.mark.integration


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


@pytest.fixture
def session() -> Iterator[Session]:
    _cleanup_trading_tables()

    session_factory = get_session_factory()
    db_session = session_factory()

    try:
        yield db_session
    finally:
        if db_session.in_transaction():
            db_session.rollback()

        db_session.close()

        _cleanup_trading_tables()


def _build_service(
    session: Session,
    *,
    bid: Decimal = Decimal("210"),
    ask: Decimal = Decimal("212"),
) -> PersistentPaperTradingService:
    provider = StaticQuoteProvider(
        quotes={
            "AAPL": RawQuote(
                symbol="AAPL",
                bid=bid,
                ask=ask,
            ),
        },
    )

    trading_service = PaperTradingService(
        quote_service=QuoteService(
            provider=provider,
        ),
        broker=PaperBroker(),
    )

    return PersistentPaperTradingService(
        trading_service=trading_service,
        unit_of_work=SqlAlchemyUnitOfWork(
            session=session,
        ),
    )


def _create_account(
    session: Session,
) -> PaperAccountModel:
    account_model = PaperAccountModel(
        id=uuid4(),
        user_id=f"limit-cancel-{uuid4()}",
        initial_cash=Decimal("100000"),
        cash_balance=Decimal("100000"),
    )

    session.add(
        account_model
    )

    session.commit()

    return account_model


def _execution_count(
    session: Session,
    *,
    account_id,
) -> int:
    statement = (
        select(
            PaperExecutionModel
        )
        .where(
            PaperExecutionModel.account_id
            == account_id
        )
    )

    return len(
        list(
            session.scalars(
                statement
            ).all()
        )
    )


def test_persisted_pending_limit_order_can_be_cancelled(
    session: Session,
) -> None:
    account_model = _create_account(
        session
    )

    service = _build_service(
        session,
    )

    order = service.submit_limit_buy(
        account_id=account_model.id,
        symbol="AAPL",
        quantity=10,
        limit_price=Decimal("200"),
    )

    assert order.status == OrderStatus.PENDING

    cancelled_order = service.cancel_limit_order(
        order_id=order.order_id,
    )

    assert (
        cancelled_order.order_id
        == order.order_id
    )

    assert (
        cancelled_order.status
        == OrderStatus.CANCELLED
    )

    assert cancelled_order.filled_quantity == 0

    session.expire_all()

    persisted_order = PaperOrderRepository(
        session=session,
    ).get(
        order.order_id
    )

    persisted_account = PaperAccountRepository(
        session=session,
    ).get(
        account_model.id
    )

    persisted_position = PaperPositionRepository(
        session=session,
    ).get(
        account_id=account_model.id,
        symbol="AAPL",
    )

    assert persisted_order is not None

    assert (
        persisted_order.status
        == OrderStatus.CANCELLED
    )

    assert persisted_order.filled_quantity == 0

    assert persisted_account is not None

    assert (
        persisted_account.cash_balance
        == Decimal("100000")
    )

    assert persisted_position is None

    assert (
        _execution_count(
            session,
            account_id=account_model.id,
        )
        == 0
    )


def test_cancelled_limit_order_cannot_fill_later(
    session: Session,
) -> None:
    account_model = _create_account(
        session
    )

    submission_service = _build_service(
        session,
        bid=Decimal("210"),
        ask=Decimal("212"),
    )

    order = submission_service.submit_limit_buy(
        account_id=account_model.id,
        symbol="AAPL",
        quantity=10,
        limit_price=Decimal("200"),
    )

    assert order.status == OrderStatus.PENDING

    cancelled_order = (
        submission_service.cancel_limit_order(
            order_id=order.order_id,
        )
    )

    assert (
        cancelled_order.status
        == OrderStatus.CANCELLED
    )

    # Quote is now marketable for the original LIMIT BUY.
    processing_service = _build_service(
        session,
        bid=Decimal("198"),
        ask=Decimal("199"),
    )

    execution = processing_service.process_limit_order(
        order_id=order.order_id,
    )

    assert execution is None

    session.expire_all()

    persisted_order = PaperOrderRepository(
        session=session,
    ).get(
        order.order_id
    )

    persisted_account = PaperAccountRepository(
        session=session,
    ).get(
        account_model.id
    )

    persisted_position = PaperPositionRepository(
        session=session,
    ).get(
        account_id=account_model.id,
        symbol="AAPL",
    )

    assert persisted_order is not None

    assert (
        persisted_order.status
        == OrderStatus.CANCELLED
    )

    assert persisted_order.filled_quantity == 0

    assert persisted_account is not None

    assert (
        persisted_account.cash_balance
        == Decimal("100000")
    )

    assert persisted_position is None

    assert (
        _execution_count(
            session,
            account_id=account_model.id,
        )
        == 0
    )