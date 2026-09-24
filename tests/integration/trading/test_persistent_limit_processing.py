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
    OrderSide,
    OrderStatus,
    OrderType,
)
from libs.trading.models import (
    PaperAccount,
    Position,
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
    """
    Remove paper-trading rows in foreign-key-safe order.

    These integration tests commit real PostgreSQL transactions,
    therefore cleanup is required both before and after each test.
    """

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
    """
    Real PostgreSQL session used by persistent LIMIT lifecycle tests.
    """

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
    bid: Decimal,
    ask: Decimal,
) -> PersistentPaperTradingService:
    """
    Build the real persistent trading service with a deterministic
    quote source.

    The database / repositories / UnitOfWork remain real.
    """

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
    *,
    initial_cash: Decimal = Decimal("100000"),
) -> PaperAccount:
    """
    Persist a paper account using the production repository.
    """

    account = PaperAccount(
        initial_cash=initial_cash,
    )

    assert account.account_id is not None

    repository = PaperAccountRepository(
        session=session,
    )

    repository.add(
        user_id=f"limit-processing-{uuid4()}",
        account=account,
    )

    session.commit()

    return account


def _create_position(
    session: Session,
    *,
    account_id,
    symbol: str = "AAPL",
    quantity: int = 10,
    average_cost: Decimal = Decimal("200"),
) -> None:
    """
    Persist an existing position for LIMIT SELL scenarios.
    """

    repository = PaperPositionRepository(
        session=session,
    )

    repository.upsert(
        account_id=account_id,
        position=Position(
            symbol=symbol,
            quantity=quantity,
            average_cost=average_cost,
            realized_pnl=Decimal("0"),
        ),
    )

    session.commit()


def _execution_rows(
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


def test_persisted_limit_buy_stays_pending_when_not_marketable(
    session: Session,
) -> None:
    """
    Persisted LIMIT BUY lifecycle:

        submit @ 200
        current ask = 212
        process
        -> remains PENDING

    No cash, position, or execution mutation is allowed.
    """

    account = _create_account(
        session
    )

    assert account.account_id is not None

    submission_service = _build_service(
        session,
        bid=Decimal("210"),
        ask=Decimal("212"),
    )

    order = submission_service.submit_limit_buy(
        account_id=account.account_id,
        symbol="aapl",
        quantity=10,
        limit_price=Decimal("200"),
    )

    assert order.status == OrderStatus.PENDING

    processing_service = _build_service(
        session,
        bid=Decimal("210"),
        ask=Decimal("212"),
    )

    execution = processing_service.process_limit_order(
        order_id=order.order_id,
    )

    assert execution is None

    session.expire_all()

    persisted_account = PaperAccountRepository(
        session=session,
    ).get(
        account.account_id
    )

    persisted_order = PaperOrderRepository(
        session=session,
    ).get(
        order.order_id
    )

    persisted_position = PaperPositionRepository(
        session=session,
    ).get(
        account_id=account.account_id,
        symbol="AAPL",
    )

    executions = _execution_rows(
        session,
        account_id=account.account_id,
    )

    assert persisted_account is not None
    assert (
        persisted_account.cash_balance
        == Decimal("100000")
    )

    assert persisted_order is not None
    assert persisted_order.side == OrderSide.BUY
    assert persisted_order.order_type == OrderType.LIMIT
    assert persisted_order.status == OrderStatus.PENDING
    assert persisted_order.quantity == 10
    assert persisted_order.filled_quantity == 0
    assert (
        persisted_order.limit_price
        == Decimal("200")
    )

    assert persisted_position is None

    assert executions == []


def test_persisted_limit_buy_fills_and_persists_complete_state(
    session: Session,
) -> None:
    """
    Persisted LIMIT BUY lifecycle:

        submit LIMIT BUY 10 @ 200
        initial ask = 212
        -> PENDING

        new ask = 199
        process persisted order
        -> FILLED @ 199

    Expected PostgreSQL state:

        cash:
            100000 - (10 * 199)
            = 98010

        position:
            10 @ 199

        order:
            FILLED, filled_quantity=10

        execution:
            exactly one row @ 199
    """

    account = _create_account(
        session
    )

    assert account.account_id is not None

    submission_service = _build_service(
        session,
        bid=Decimal("210"),
        ask=Decimal("212"),
    )

    order = submission_service.submit_limit_buy(
        account_id=account.account_id,
        symbol="aapl",
        quantity=10,
        limit_price=Decimal("200"),
    )

    assert order.status == OrderStatus.PENDING
    assert order.filled_quantity == 0

    session.expire_all()

    persisted_pending_order = PaperOrderRepository(
        session=session,
    ).get(
        order.order_id
    )

    assert persisted_pending_order is not None
    assert (
        persisted_pending_order.status
        == OrderStatus.PENDING
    )
    assert persisted_pending_order.filled_quantity == 0

    processing_service = _build_service(
        session,
        bid=Decimal("198"),
        ask=Decimal("199"),
    )

    execution = processing_service.process_limit_order(
        order_id=order.order_id,
    )

    assert execution is not None
    assert execution.order_id == order.order_id
    assert execution.side == OrderSide.BUY
    assert execution.symbol == "AAPL"
    assert execution.quantity == 10
    assert (
        execution.price
        == Decimal("199")
    )

    session.expire_all()

    persisted_account = PaperAccountRepository(
        session=session,
    ).get(
        account.account_id
    )

    persisted_order = PaperOrderRepository(
        session=session,
    ).get(
        order.order_id
    )

    persisted_position = PaperPositionRepository(
        session=session,
    ).get(
        account_id=account.account_id,
        symbol="AAPL",
    )

    executions = _execution_rows(
        session,
        account_id=account.account_id,
    )

    assert persisted_account is not None

    assert (
        persisted_account.cash_balance
        == Decimal("98010")
    )

    assert persisted_order is not None
    assert persisted_order.side == OrderSide.BUY
    assert persisted_order.order_type == OrderType.LIMIT
    assert persisted_order.status == OrderStatus.FILLED
    assert persisted_order.quantity == 10
    assert persisted_order.filled_quantity == 10
    assert (
        persisted_order.limit_price
        == Decimal("200")
    )

    assert persisted_position is not None
    assert persisted_position.symbol == "AAPL"
    assert persisted_position.quantity == 10

    assert (
        persisted_position.average_cost
        == Decimal("199")
    )

    assert (
        persisted_position.realized_pnl
        == Decimal("0")
    )

    assert len(executions) == 1

    persisted_execution = executions[0]

    assert (
        persisted_execution.order_id
        == order.order_id
    )

    assert (
        persisted_execution.account_id
        == account.account_id
    )

    assert persisted_execution.symbol == "AAPL"
    assert persisted_execution.side == OrderSide.BUY.value
    assert persisted_execution.quantity == 10

    assert (
        persisted_execution.price
        == Decimal("199")
    )


def test_persisted_limit_sell_stays_pending_when_not_marketable(
    session: Session,
) -> None:
    """
    Persisted LIMIT SELL lifecycle:

        existing position = 10 @ 200
        submit SELL 5 @ 220
        current bid = 210
        process
        -> remains PENDING

    Account and position must remain unchanged.
    """

    account = _create_account(
        session
    )

    assert account.account_id is not None

    _create_position(
        session,
        account_id=account.account_id,
        symbol="AAPL",
        quantity=10,
        average_cost=Decimal("200"),
    )

    submission_service = _build_service(
        session,
        bid=Decimal("210"),
        ask=Decimal("212"),
    )

    order = submission_service.submit_limit_sell(
        account_id=account.account_id,
        symbol="aapl",
        quantity=5,
        limit_price=Decimal("220"),
    )

    assert order.status == OrderStatus.PENDING

    processing_service = _build_service(
        session,
        bid=Decimal("210"),
        ask=Decimal("212"),
    )

    execution = processing_service.process_limit_order(
        order_id=order.order_id,
    )

    assert execution is None

    session.expire_all()

    persisted_account = PaperAccountRepository(
        session=session,
    ).get(
        account.account_id
    )

    persisted_order = PaperOrderRepository(
        session=session,
    ).get(
        order.order_id
    )

    persisted_position = PaperPositionRepository(
        session=session,
    ).get(
        account_id=account.account_id,
        symbol="AAPL",
    )

    executions = _execution_rows(
        session,
        account_id=account.account_id,
    )

    assert persisted_account is not None

    assert (
        persisted_account.cash_balance
        == Decimal("100000")
    )

    assert persisted_order is not None
    assert persisted_order.side == OrderSide.SELL
    assert persisted_order.order_type == OrderType.LIMIT
    assert persisted_order.status == OrderStatus.PENDING
    assert persisted_order.quantity == 5
    assert persisted_order.filled_quantity == 0

    assert persisted_position is not None
    assert persisted_position.quantity == 10

    assert (
        persisted_position.average_cost
        == Decimal("200")
    )

    assert (
        persisted_position.realized_pnl
        == Decimal("0")
    )

    assert executions == []


def test_persisted_limit_sell_fills_and_persists_complete_state(
    session: Session,
) -> None:
    """
    Persisted LIMIT SELL lifecycle:

        position:
            10 @ 200

        submit:
            SELL 5 @ 220

        new bid:
            225

        fill:
            5 @ 225

    Expected PostgreSQL state:

        cash:
            100000 + (5 * 225)
            = 101125

        remaining position:
            quantity = 5
            average_cost = 200

        realized PnL:
            (225 - 200) * 5
            = 125

        execution:
            exactly one row @ 225
    """

    account = _create_account(
        session
    )

    assert account.account_id is not None

    _create_position(
        session,
        account_id=account.account_id,
        symbol="AAPL",
        quantity=10,
        average_cost=Decimal("200"),
    )

    submission_service = _build_service(
        session,
        bid=Decimal("210"),
        ask=Decimal("212"),
    )

    order = submission_service.submit_limit_sell(
        account_id=account.account_id,
        symbol="aapl",
        quantity=5,
        limit_price=Decimal("220"),
    )

    assert order.status == OrderStatus.PENDING
    assert order.filled_quantity == 0

    session.expire_all()

    persisted_pending_order = PaperOrderRepository(
        session=session,
    ).get(
        order.order_id
    )

    assert persisted_pending_order is not None
    assert (
        persisted_pending_order.status
        == OrderStatus.PENDING
    )

    processing_service = _build_service(
        session,
        bid=Decimal("225"),
        ask=Decimal("226"),
    )

    execution = processing_service.process_limit_order(
        order_id=order.order_id,
    )

    assert execution is not None

    assert execution.order_id == order.order_id
    assert execution.side == OrderSide.SELL
    assert execution.symbol == "AAPL"
    assert execution.quantity == 5

    assert (
        execution.price
        == Decimal("225")
    )

    session.expire_all()

    persisted_account = PaperAccountRepository(
        session=session,
    ).get(
        account.account_id
    )

    persisted_order = PaperOrderRepository(
        session=session,
    ).get(
        order.order_id
    )

    persisted_position = PaperPositionRepository(
        session=session,
    ).get(
        account_id=account.account_id,
        symbol="AAPL",
    )

    executions = _execution_rows(
        session,
        account_id=account.account_id,
    )

    assert persisted_account is not None

    assert (
        persisted_account.cash_balance
        == Decimal("101125")
    )

    assert persisted_order is not None
    assert persisted_order.side == OrderSide.SELL
    assert persisted_order.order_type == OrderType.LIMIT
    assert persisted_order.status == OrderStatus.FILLED
    assert persisted_order.quantity == 5
    assert persisted_order.filled_quantity == 5

    assert (
        persisted_order.limit_price
        == Decimal("220")
    )

    assert persisted_position is not None
    assert persisted_position.symbol == "AAPL"
    assert persisted_position.quantity == 5

    assert (
        persisted_position.average_cost
        == Decimal("200")
    )

    assert (
        persisted_position.realized_pnl
        == Decimal("125")
    )

    assert len(executions) == 1

    persisted_execution = executions[0]

    assert (
        persisted_execution.order_id
        == order.order_id
    )

    assert (
        persisted_execution.account_id
        == account.account_id
    )

    assert persisted_execution.symbol == "AAPL"
    assert persisted_execution.side == OrderSide.SELL.value
    assert persisted_execution.quantity == 5

    assert (
        persisted_execution.price
        == Decimal("225")
    )