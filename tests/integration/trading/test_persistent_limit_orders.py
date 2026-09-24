from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from libs.database.models.trading import PaperExecutionModel
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


@pytest.fixture
def session() -> Iterator[Session]:
    """
    Real PostgreSQL SQLAlchemy session used by integration tests.

    The application session factory owns engine configuration.
    The fixture owns the Session lifecycle only.
    """

    session_factory = get_session_factory()
    db_session = session_factory()

    try:
        yield db_session
    finally:
        db_session.rollback()
        db_session.close()


def _build_service(
    session: Session,
) -> PersistentPaperTradingService:
    """
    Build the real persistent paper-trading application service
    while using a deterministic quote provider.

    AAPL quote:

        bid = 210
        ask = 212
    """

    quote_provider = StaticQuoteProvider(
        quotes={
            "AAPL": RawQuote(
                symbol="AAPL",
                bid=Decimal("210"),
                ask=Decimal("212"),
            ),
        },
    )

    quote_service = QuoteService(
        provider=quote_provider,
    )

    trading_service = PaperTradingService(
        quote_service=quote_service,
        broker=PaperBroker(),
    )

    unit_of_work = SqlAlchemyUnitOfWork(
        session
    )

    return PersistentPaperTradingService(
        trading_service=trading_service,
        unit_of_work=unit_of_work,
    )


def _create_account(
    session: Session,
    *,
    initial_cash: Decimal = Decimal("100000"),
) -> PaperAccount:
    """
    Persist a paper account for an integration test.

    PaperAccountRepository.add() requires both:
    - user_id;
    - account.
    """

    account = PaperAccount(
        initial_cash=initial_cash,
    )

    repository = PaperAccountRepository(
        session
    )

    repository.add(
        user_id=uuid4(),
        account=account,
    )

    session.commit()

    assert account.account_id is not None

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
    Persist an initial position used by LIMIT SELL tests.
    """

    repository = PaperPositionRepository(
        session
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


def _execution_count(
    session: Session,
    *,
    account_id,
) -> int:
    """
    Count persisted execution rows belonging to one paper account.
    """

    statement = (
        select(
            func.count(
                PaperExecutionModel.id
            )
        )
        .where(
            PaperExecutionModel.account_id
            == account_id
        )
    )

    count = session.scalar(
        statement
    )

    assert count is not None

    return count


def test_limit_buy_persists_pending_order_without_mutating_account(
    session: Session,
) -> None:
    """
    LIMIT BUY submission must:

    - persist a PENDING LIMIT BUY order;
    - normalize symbol to AAPL;
    - preserve account cash;
    - not create a position;
    - not create an execution.

    No cash reservation is implemented at submission time.
    """

    account = _create_account(
        session
    )

    assert account.account_id is not None

    service = _build_service(
        session
    )

    order = service.submit_limit_buy(
        account_id=account.account_id,
        symbol="aapl",
        quantity=10,
        limit_price=Decimal("200"),
    )

    # ----------------------------------------------------------
    # Domain result
    # ----------------------------------------------------------

    assert order.account_id == account.account_id
    assert order.symbol == "AAPL"

    assert order.side == OrderSide.BUY
    assert order.order_type == OrderType.LIMIT
    assert order.status == OrderStatus.PENDING

    assert order.quantity == 10
    assert order.filled_quantity == 0

    assert (
        order.limit_price
        == Decimal("200")
    )

    # Force subsequent reads to come from PostgreSQL.
    session.expire_all()

    # ----------------------------------------------------------
    # Reload committed database state
    # ----------------------------------------------------------

    persisted_account = PaperAccountRepository(
        session
    ).get(
        account.account_id
    )

    persisted_position = PaperPositionRepository(
        session
    ).get(
        account_id=account.account_id,
        symbol="AAPL",
    )

    persisted_order = PaperOrderRepository(
        session
    ).get(
        order.order_id
    )

    execution_count = _execution_count(
        session,
        account_id=account.account_id,
    )

    # ----------------------------------------------------------
    # Account must remain unchanged
    # ----------------------------------------------------------

    assert persisted_account is not None

    assert (
        persisted_account.cash_balance
        == Decimal("100000")
    )

    # ----------------------------------------------------------
    # LIMIT BUY submission must not create a position
    # ----------------------------------------------------------

    assert persisted_position is None

    # ----------------------------------------------------------
    # Order must be committed as PENDING
    # ----------------------------------------------------------

    assert persisted_order is not None

    assert (
        persisted_order.order_id
        == order.order_id
    )

    assert (
        persisted_order.account_id
        == account.account_id
    )

    assert persisted_order.symbol == "AAPL"

    assert (
        persisted_order.side
        == OrderSide.BUY
    )

    assert (
        persisted_order.order_type
        == OrderType.LIMIT
    )

    assert (
        persisted_order.status
        == OrderStatus.PENDING
    )

    assert persisted_order.quantity == 10

    assert (
        persisted_order.filled_quantity
        == 0
    )

    assert (
        persisted_order.limit_price
        == Decimal("200")
    )

    # ----------------------------------------------------------
    # No execution before LIMIT order fill
    # ----------------------------------------------------------

    assert execution_count == 0


def test_limit_sell_persists_pending_order_without_mutating_position(
    session: Session,
) -> None:
    """
    LIMIT SELL submission must:

    - persist a PENDING LIMIT SELL order;
    - preserve account cash;
    - preserve existing position quantity;
    - preserve average cost;
    - preserve realized PnL;
    - not create an execution.

    Inventory reservation is intentionally not implemented at
    submission time.
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

    service = _build_service(
        session
    )

    order = service.submit_limit_sell(
        account_id=account.account_id,
        symbol="aapl",
        quantity=5,
        limit_price=Decimal("220"),
    )

    # ----------------------------------------------------------
    # Domain result
    # ----------------------------------------------------------

    assert order.account_id == account.account_id
    assert order.symbol == "AAPL"

    assert order.side == OrderSide.SELL
    assert order.order_type == OrderType.LIMIT
    assert order.status == OrderStatus.PENDING

    assert order.quantity == 5
    assert order.filled_quantity == 0

    assert (
        order.limit_price
        == Decimal("220")
    )

    # Force subsequent reads to come from PostgreSQL.
    session.expire_all()

    # ----------------------------------------------------------
    # Reload committed database state
    # ----------------------------------------------------------

    persisted_account = PaperAccountRepository(
        session
    ).get(
        account.account_id
    )

    persisted_position = PaperPositionRepository(
        session
    ).get(
        account_id=account.account_id,
        symbol="AAPL",
    )

    persisted_order = PaperOrderRepository(
        session
    ).get(
        order.order_id
    )

    execution_count = _execution_count(
        session,
        account_id=account.account_id,
    )

    # ----------------------------------------------------------
    # Account cash must remain unchanged
    # ----------------------------------------------------------

    assert persisted_account is not None

    assert (
        persisted_account.cash_balance
        == Decimal("100000")
    )

    # ----------------------------------------------------------
    # Existing position must remain unchanged
    # ----------------------------------------------------------

    assert persisted_position is not None

    assert (
        persisted_position.symbol
        == "AAPL"
    )

    assert (
        persisted_position.quantity
        == 10
    )

    assert (
        persisted_position.average_cost
        == Decimal("200")
    )

    assert (
        persisted_position.realized_pnl
        == Decimal("0")
    )

    # ----------------------------------------------------------
    # Order must be committed as PENDING
    # ----------------------------------------------------------

    assert persisted_order is not None

    assert (
        persisted_order.order_id
        == order.order_id
    )

    assert (
        persisted_order.account_id
        == account.account_id
    )

    assert persisted_order.symbol == "AAPL"

    assert (
        persisted_order.side
        == OrderSide.SELL
    )

    assert (
        persisted_order.order_type
        == OrderType.LIMIT
    )

    assert (
        persisted_order.status
        == OrderStatus.PENDING
    )

    assert persisted_order.quantity == 5

    assert (
        persisted_order.filled_quantity
        == 0
    )

    assert (
        persisted_order.limit_price
        == Decimal("220")
    )

    # ----------------------------------------------------------
    # No execution before LIMIT order fill
    # ----------------------------------------------------------

    assert execution_count == 0