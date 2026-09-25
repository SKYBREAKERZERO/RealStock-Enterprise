from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
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
from libs.trading.enums import OrderSide, OrderStatus
from libs.trading.execution import Execution
from libs.trading.models import PaperAccount
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


@pytest.fixture(autouse=True)
def clean_trading_tables() -> Iterator[None]:
    """
    Each concurrency test owns all paper-trading rows.

    Real commits occur from multiple worker sessions, so cleanup is
    performed before and after the test.
    """

    _cleanup_trading_tables()

    try:
        yield
    finally:
        _cleanup_trading_tables()


def _build_service(
    session: Session,
    *,
    bid: Decimal,
    ask: Decimal,
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
) -> PaperAccount:
    account = PaperAccount(
        initial_cash=Decimal("100000"),
    )

    repository = PaperAccountRepository(
        session=session,
    )

    repository.add(
        user_id=f"limit-concurrency-{uuid4()}",
        account=account,
    )

    session.commit()

    return account


def _load_executions(
    session: Session,
    *,
    account_id,
) -> list[PaperExecutionModel]:
    statement = (
        select(
            PaperExecutionModel
        )
        .where(
            PaperExecutionModel.account_id
            == account_id
        )
    )

    return list(
        session.scalars(
            statement
        ).all()
    )


def test_same_persisted_limit_order_cannot_be_double_filled() -> None:
    """
    Two independent PostgreSQL workers process the same marketable
    persisted LIMIT BUY concurrently.

    Required invariant:

        one order
        -> one fill
        -> one execution
        -> one cash debit
        -> one position increase

    The second worker must observe the state committed by the first
    worker after PostgreSQL row-lock serialization and must not produce
    another execution.
    """

    session_factory = get_session_factory()

    # ----------------------------------------------------------
    # Arrange persisted PENDING order.
    # ----------------------------------------------------------

    with session_factory() as setup_session:
        account = _create_account(
            setup_session
        )

        account_id = account.account_id

        submission_service = _build_service(
            setup_session,
            bid=Decimal("210"),
            ask=Decimal("212"),
        )

        order = submission_service.submit_limit_buy(
            account_id=account_id,
            symbol="AAPL",
            quantity=10,
            limit_price=Decimal("200"),
        )

        order_id = order.order_id

        assert order.status == OrderStatus.PENDING
        assert order.filled_quantity == 0

    # Both workers wait here before entering process_limit_order().
    #
    # Each worker owns its own SQLAlchemy Session. A Session must never
    # be shared between threads.
    start_barrier = Barrier(2)

    def process_order_worker() -> Execution | None:
        with session_factory() as worker_session:
            service = _build_service(
                worker_session,
                bid=Decimal("198"),
                ask=Decimal("199"),
            )

            start_barrier.wait(
                timeout=5
            )

            return service.process_limit_order(
                order_id=order_id,
            )

    # ----------------------------------------------------------
    # Act: two workers race on the same order.
    # ----------------------------------------------------------

    with ThreadPoolExecutor(
        max_workers=2
    ) as executor:
        future_a = executor.submit(
            process_order_worker
        )

        future_b = executor.submit(
            process_order_worker
        )

        result_a = future_a.result(
            timeout=10
        )

        result_b = future_b.result(
            timeout=10
        )

    results = [
        result_a,
        result_b,
    ]

    successful_executions = [
        result
        for result in results
        if result is not None
    ]

    # Exactly one worker may create an execution.
    assert len(successful_executions) == 1

    execution = successful_executions[0]

    assert execution.order_id == order_id
    assert execution.symbol == "AAPL"
    assert execution.side == OrderSide.BUY
    assert execution.quantity == 10

    assert (
        execution.price
        == Decimal("199")
    )

    # ----------------------------------------------------------
    # Assert final committed PostgreSQL state.
    # ----------------------------------------------------------

    with session_factory() as verification_session:
        persisted_account = PaperAccountRepository(
            session=verification_session,
        ).get(
            account_id
        )

        persisted_order = PaperOrderRepository(
            session=verification_session,
        ).get(
            order_id
        )

        persisted_position = PaperPositionRepository(
            session=verification_session,
        ).get(
            account_id=account_id,
            symbol="AAPL",
        )

        persisted_executions = _load_executions(
            verification_session,
            account_id=account_id,
        )

        assert persisted_account is not None

        # Debit must occur exactly once:
        #
        # 100000 - 10 * 199 = 98010
        assert (
            persisted_account.cash_balance
            == Decimal("98010")
        )

        assert persisted_order is not None

        assert (
            persisted_order.status
            == OrderStatus.FILLED
        )

        assert persisted_order.quantity == 10
        assert persisted_order.filled_quantity == 10

        assert persisted_position is not None
        assert persisted_position.symbol == "AAPL"
        assert persisted_position.quantity == 10

        assert (
            persisted_position.average_cost
            == Decimal("199")
        )

        # This is the primary double-fill invariant.
        assert len(persisted_executions) == 1

        persisted_execution = (
            persisted_executions[0]
        )

        assert (
            persisted_execution.order_id
            == order_id
        )

        assert (
            persisted_execution.account_id
            == account_id
        )

        assert persisted_execution.symbol == "AAPL"

        assert (
            persisted_execution.side
            == OrderSide.BUY.value
        )

        assert persisted_execution.quantity == 10

        assert (
            persisted_execution.price
            == Decimal("199")
        )