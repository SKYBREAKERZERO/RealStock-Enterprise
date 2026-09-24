from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Event
from time import sleep
from uuid import uuid4

import pytest
from sqlalchemy import (
    delete,
    select,
)

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


@pytest.fixture
def session_factory():
    factory = get_session_factory()

    yield factory

    with factory() as session:
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

            # Give Session B time to reach
            # SELECT ... FOR UPDATE.
            #
            # Session A still owns the account lock,
            # therefore Session B must remain blocked.
            sleep(0.2)

            assert not worker_finished.is_set()

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

        assert (
            verification_session.query(
                PaperOrderModel
            ).count()
            == 0
        )

        assert (
            verification_session.query(
                PaperExecutionModel
            ).count()
            == 0
        )

        assert (
            verification_session.query(
                PaperPositionModel
            ).count()
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

    with session_factory() as setup_session:
        setup_session.add(
            PaperPositionModel(
                account_id=account.account_id,
                symbol="AAPL",
                quantity=10,
                average_cost=Decimal("200"),
                realized_pnl=Decimal("0"),
            )
        )

        setup_session.commit()

    lock_acquired = Event()
    worker_started = Event()
    worker_finished = Event()

    result: dict[str, object] = {}

    session_a = session_factory()

    try:
        account_repository = PaperAccountRepository(
            session=session_a,
        )

        locked_account = (
            account_repository.get_for_update(
                account.account_id
            )
        )

        assert locked_account is not None

        position_repository = PaperPositionRepository(
            session=session_a,
        )

        locked_position = (
            position_repository.get_for_update(
                account_id=account.account_id,
                symbol="AAPL",
            )
        )

        assert locked_position is not None

        assert locked_position.quantity == 10

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
                        quantity=10,
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

            # Session B should block on the account row lock
            # held by Session A.
            sleep(0.2)

            assert not worker_finished.is_set()

            # Simulate Session A consuming the complete position.
            locked_position.sell(
                quantity=10,
                price=Decimal("210"),
            )

            locked_account.credit(
                Decimal("2100")
            )

            account_repository.update(
                locked_account
            )

            position_repository.upsert(
                account_id=account.account_id,
                position=locked_position,
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
        InsufficientPositionError,
    )

    assert "success" not in result

    with session_factory() as verification_session:
        stored_position = verification_session.scalar(
            select(
                PaperPositionModel
            ).where(
                PaperPositionModel.account_id
                == account.account_id,
                PaperPositionModel.symbol
                == "AAPL",
            )
        )

        assert stored_position is not None

        assert stored_position.quantity == 0

        assert (
            stored_position.realized_pnl
            == Decimal("100")
        )

        stored_account = verification_session.get(
            PaperAccountModel,
            account.account_id,
        )

        assert stored_account is not None

        assert (
            stored_account.cash_balance
            == Decimal("102100")
        )

        assert (
            verification_session.query(
                PaperOrderModel
            ).count()
            == 0
        )

        assert (
            verification_session.query(
                PaperExecutionModel
            ).count()
            == 0
        )