from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Event
from time import sleep
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete

from libs.database.models import (
    PaperAccountModel,
    PaperExecutionModel,
    PaperOrderModel,
    PaperPositionModel,
)
from libs.database.repositories.trading import (
    PaperAccountRepository,
    PaperPositionRepository,
)
from libs.database.session import get_session_factory
from libs.database.unit_of_work import SqlAlchemyUnitOfWork
from libs.trading.exceptions import (
    InsufficientBuyingPowerError,
    InsufficientPositionError,
)
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


def _build_service(
    session,
) -> PersistentPaperTradingService:
    provider = StaticQuoteProvider(
        quotes={
            "AAPL": RawQuote(
                symbol="AAPL",
                bid=Decimal("210"),
                ask=Decimal("212"),
            )
        }
    )

    trading_service = PaperTradingService(
        broker=PaperBroker(),
        quote_service=QuoteService(
            provider=provider,
        ),
    )

    return PersistentPaperTradingService(
        trading_service=trading_service,
        unit_of_work=SqlAlchemyUnitOfWork(
            session=session,
        ),
    )


def _cleanup_trading_tables(
    session_factory,
) -> None:
    """
    Remove paper-trading rows in foreign-key-safe order.

    These tests use the real PostgreSQL database and therefore must
    not depend on rows left behind by another integration-test run.
    """

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
def session_factory():
    factory = get_session_factory()

    # Protect this test module from rows left by a previous test run.
    _cleanup_trading_tables(
        factory
    )

    try:
        yield factory
    finally:
        _cleanup_trading_tables(
            factory
        )


def _create_account(
    session_factory,
    *,
    initial_cash: Decimal,
) -> PaperAccount:
    account = PaperAccount(
        initial_cash=initial_cash,
    )

    assert account.account_id is not None

    with session_factory() as session:
        session.add(
            PaperAccountModel(
                id=account.account_id,
                user_id=f"concurrency-{uuid4()}",
                initial_cash=account.initial_cash,
                cash_balance=account.cash_balance,
            )
        )

        session.commit()

    return account


def _create_position(
    session_factory,
    *,
    account_id: UUID,
    symbol: str = "AAPL",
    quantity: int = 10,
    average_cost: Decimal = Decimal("200"),
) -> None:
    with session_factory() as session:
        session.add(
            PaperPositionModel(
                account_id=account_id,
                symbol=symbol,
                quantity=quantity,
                average_cost=average_cost,
                realized_pnl=Decimal("0"),
            )
        )

        session.commit()


def test_account_row_lock_blocks_trade_until_latest_balance_is_visible(
    session_factory,
) -> None:
    account = _create_account(
        session_factory,
        initial_cash=Decimal("300"),
    )

    assert account.account_id is not None

    lock_acquired = Event()
    worker_started = Event()
    worker_finished = Event()

    result: dict[str, object] = {}

    session_a = session_factory()

    try:
        repository = PaperAccountRepository(
            session=session_a,
        )

        locked_account = repository.get_for_update(
            account.account_id
        )

        assert locked_account is not None

        assert (
            locked_account.cash_balance
            == Decimal("300")
        )

        lock_acquired.set()

        def execute_competing_buy() -> None:
            assert lock_acquired.wait(
                timeout=5
            )

            worker_started.set()

            session_b = session_factory()

            try:
                service = _build_service(
                    session_b
                )

                try:
                    service.market_buy(
                        account_id=account.account_id,
                        symbol="AAPL",
                        quantity=1,
                    )
                except Exception as exc:
                    result["exception"] = exc
                else:
                    result["success"] = True
            finally:
                session_b.close()
                worker_finished.set()

        with ThreadPoolExecutor(
            max_workers=1
        ) as executor:
            future = executor.submit(
                execute_competing_buy
            )

            assert worker_started.wait(
                timeout=5
            )

            # Session B reaches the production
            # SELECT ... FOR UPDATE path.
            #
            # Session A already owns the account row lock,
            # therefore Session B must still be blocked.
            sleep(0.2)

            assert not worker_finished.is_set()

            # Simulate another committed operation consuming
            # part of the account buying power while Session B
            # is waiting for the account row lock.
            locked_account.cash_balance = Decimal(
                "88"
            )

            repository.update(
                locked_account
            )

            session_a.commit()

            future.result(
                timeout=5
            )

    finally:
        if session_a.in_transaction():
            session_a.rollback()

        session_a.close()

    assert worker_finished.is_set()

    assert isinstance(
        result.get("exception"),
        InsufficientBuyingPowerError,
    )

    assert "success" not in result

    with session_factory() as verification_session:
        stored_account = verification_session.get(
            PaperAccountModel,
            account.account_id,
        )

        assert stored_account is not None

        assert (
            stored_account.cash_balance
            == Decimal("88")
        )

        # The rejected competing BUY must not persist an order
        # for this account.
        assert (
            verification_session.query(
                PaperOrderModel
            )
            .filter(
                PaperOrderModel.account_id
                == account.account_id
            )
            .count()
            == 0
        )

        # The rejected competing BUY must not persist execution.
        assert (
            verification_session.query(
                PaperExecutionModel
            )
            .filter(
                PaperExecutionModel.account_id
                == account.account_id
            )
            .count()
            == 0
        )

        # The rejected BUY must not create a position.
        assert (
            verification_session.query(
                PaperPositionModel
            )
            .filter(
                PaperPositionModel.account_id
                == account.account_id
            )
            .count()
            == 0
        )


def test_account_row_lock_prevents_concurrent_oversell(
    session_factory,
) -> None:
    account = _create_account(
        session_factory,
        initial_cash=Decimal("100000"),
    )

    assert account.account_id is not None

    _create_position(
        session_factory,
        account_id=account.account_id,
        symbol="AAPL",
        quantity=10,
        average_cost=Decimal("200"),
    )

    lock_acquired = Event()
    worker_started = Event()
    worker_finished = Event()

    result: dict[str, object] = {}

    session_a = session_factory()

    try:
        account_repository = PaperAccountRepository(
            session=session_a,
        )

        position_repository = PaperPositionRepository(
            session=session_a,
        )

        # Keep the same lock ordering as the production service:
        #
        # Account FOR UPDATE
        #     ->
        # Position FOR UPDATE
        locked_account = (
            account_repository.get_for_update(
                account.account_id
            )
        )

        assert locked_account is not None

        locked_position = (
            position_repository.get_for_update(
                account_id=account.account_id,
                symbol="AAPL",
            )
        )

        assert locked_position is not None

        assert (
            locked_account.cash_balance
            == Decimal("100000")
        )

        assert locked_position.quantity == 10

        assert (
            locked_position.average_cost
            == Decimal("200")
        )

        lock_acquired.set()

        def execute_competing_sell() -> None:
            assert lock_acquired.wait(
                timeout=5
            )

            worker_started.set()

            session_b = session_factory()

            try:
                service = _build_service(
                    session_b
                )

                try:
                    service.market_sell(
                        account_id=account.account_id,
                        symbol="AAPL",
                        quantity=1,
                    )
                except Exception as exc:
                    result["exception"] = exc
                else:
                    result["success"] = True
            finally:
                session_b.close()
                worker_finished.set()

        with ThreadPoolExecutor(
            max_workers=1
        ) as executor:
            future = executor.submit(
                execute_competing_sell
            )

            assert worker_started.wait(
                timeout=5
            )

            # Session B must be blocked on the account lock.
            sleep(0.2)

            assert not worker_finished.is_set()

            # Session A consumes the complete 10-share position.
            #
            # 10 * 210 = 2100 cash proceeds.
            #
            # Cost basis:
            # 10 * 200 = 2000
            #
            # Realized profit:
            # 2100 - 2000 = 100
            locked_account.cash_balance = Decimal(
                "102100"
            )

            locked_position.quantity = 0

            locked_position.realized_pnl = Decimal(
                "100"
            )

            account_repository.update(
                locked_account
            )

            position_repository.upsert(
                account_id=account.account_id,
                position=locked_position,
            )

            session_a.commit()

            # Session B can now acquire the account lock, then
            # observes the latest position quantity == 0 and
            # must reject the competing SELL.
            future.result(
                timeout=5
            )

    finally:
        if session_a.in_transaction():
            session_a.rollback()

        session_a.close()

    assert worker_finished.is_set()

    assert isinstance(
        result.get("exception"),
        InsufficientPositionError,
    )

    assert "success" not in result

    with session_factory() as verification_session:
        stored_account = verification_session.get(
            PaperAccountModel,
            account.account_id,
        )

        assert stored_account is not None

        assert (
            stored_account.cash_balance
            == Decimal("102100")
        )

        stored_position = (
            verification_session.query(
                PaperPositionModel
            )
            .filter(
                PaperPositionModel.account_id
                == account.account_id,
                PaperPositionModel.symbol
                == "AAPL",
            )
            .one_or_none()
        )

        assert stored_position is not None

        assert stored_position.quantity == 0

        assert (
            stored_position.realized_pnl
            == Decimal("100")
        )

        # Session A deliberately mutates account / position state
        # directly for concurrency setup.
        #
        # The rejected competing SELL must therefore create no
        # order for this account.
        assert (
            verification_session.query(
                PaperOrderModel
            )
            .filter(
                PaperOrderModel.account_id
                == account.account_id
            )
            .count()
            == 0
        )

        # Nor may the rejected competing SELL create an execution.
        assert (
            verification_session.query(
                PaperExecutionModel
            )
            .filter(
                PaperExecutionModel.account_id
                == account.account_id
            )
            .count()
            == 0
        )