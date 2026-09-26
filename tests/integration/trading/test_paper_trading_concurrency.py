from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Event
from time import sleep
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from libs.database.models import (
    PaperAccountModel,
    PaperExecutionModel,
    PaperOrderModel,
    PaperPositionModel,
)
from libs.database.repositories.trading import PaperAccountRepository
from libs.database.session import get_session_factory
from libs.database.unit_of_work import SqlAlchemyUnitOfWork
from libs.trading.exceptions import (
    InsufficientBuyingPowerError,
    InsufficientPositionError,
)
from libs.trading.models import PaperAccount
from libs.trading.paper_broker import PaperBroker
from services.trading.paper_trading_service import PaperTradingService
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
        session.execute(delete(PaperExecutionModel))
        session.execute(delete(PaperOrderModel))
        session.execute(delete(PaperPositionModel))
        session.execute(delete(PaperAccountModel))
        session.commit()


@pytest.fixture(autouse=True)
def clean_trading_tables() -> Iterator[None]:
    _cleanup_trading_tables()

    try:
        yield
    finally:
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
    *,
    initial_cash: Decimal,
) -> PaperAccount:
    account = PaperAccount(
        initial_cash=initial_cash,
    )

    repository = PaperAccountRepository(
        session=session,
    )

    repository.add(
        user_id=f"concurrency-{uuid4()}",
        account=account,
    )

    session.commit()

    return account


def _count_orders(
    session: Session,
    *,
    account_id,
) -> int:
    statement = (
        select(func.count())
        .select_from(PaperOrderModel)
        .where(
            PaperOrderModel.account_id
            == account_id
        )
    )

    return int(
        session.scalar(statement)
        or 0
    )


def _count_executions(
    session: Session,
    *,
    account_id,
) -> int:
    statement = (
        select(func.count())
        .select_from(PaperExecutionModel)
        .where(
            PaperExecutionModel.account_id
            == account_id
        )
    )

    return int(
        session.scalar(statement)
        or 0
    )


def test_account_row_lock_blocks_trade_until_latest_balance_is_visible() -> None:
    """
    A competing MARKET BUY must wait for the account row lock.

    Transaction A:
        - locks the account;
        - changes cash from 300 to 88;
        - commits.

    Transaction B:
        - attempts MARKET BUY 1 AAPL @ ask 212;
        - must wait for A;
        - after A commits, must observe cash=88;
        - must reject with InsufficientBuyingPowerError.

    The stale pre-lock balance of 300 must never be used to authorize
    the competing trade.
    """

    session_factory = get_session_factory()

    with session_factory() as setup_session:
        account = _create_account(
            setup_session,
            initial_cash=Decimal("300"),
        )

        account_id = account.account_id

    worker_started = Event()

    with session_factory() as lock_session:
        locked_account = lock_session.scalar(
            select(PaperAccountModel)
            .where(
                PaperAccountModel.id
                == account_id
            )
            .with_for_update()
        )

        assert locked_account is not None

        # Keep the PostgreSQL row lock open while the competing worker
        # tries to enter PersistentPaperTradingService.market_buy().
        locked_account.cash_balance = Decimal("88")

        def competing_buy() -> str:
            with session_factory() as worker_session:
                service = _build_service(
                    worker_session,
                    bid=Decimal("210"),
                    ask=Decimal("212"),
                )

                worker_started.set()

                with pytest.raises(
                    InsufficientBuyingPowerError
                ):
                    service.market_buy(
                        account_id=account_id,
                        symbol="AAPL",
                        quantity=1,
                    )

                return "rejected"

        with ThreadPoolExecutor(
            max_workers=1
        ) as executor:
            future = executor.submit(
                competing_buy
            )

            assert worker_started.wait(
                timeout=5
            )

            # B is waiting on SELECT ... FOR UPDATE held by A.
            sleep(0.2)

            assert not future.done()

            # Publish the latest balance and release the account lock.
            lock_session.commit()

            assert (
                future.result(
                    timeout=5
                )
                == "rejected"
            )

    with session_factory() as verification_session:
        persisted_account = verification_session.get(
            PaperAccountModel,
            account_id,
        )

        assert persisted_account is not None

        assert (
            persisted_account.cash_balance
            == Decimal("88")
        )

        # The competing BUY was rejected before any trade state could
        # be persisted.
        assert (
            _count_orders(
                verification_session,
                account_id=account_id,
            )
            == 0
        )

        assert (
            _count_executions(
                verification_session,
                account_id=account_id,
            )
            == 0
        )

        position = verification_session.scalar(
            select(PaperPositionModel)
            .where(
                PaperPositionModel.account_id
                == account_id,
                PaperPositionModel.symbol
                == "AAPL",
            )
        )

        assert position is None


def test_account_row_lock_prevents_concurrent_oversell() -> None:
    """
    A competing MARKET SELL must see the latest committed position.

    Initial state:
        cash = 100000
        AAPL = 10 @ 200

    Transaction A represents another SELL that owns the account lock:
        - consumes all 10 shares at bid 210;
        - cash becomes 102100;
        - position quantity becomes 0;
        - realized PnL becomes 100;
        - commits.

    Transaction B concurrently attempts to sell another 10 shares.
    It must block on the account row, then observe quantity=0 and fail
    with InsufficientPositionError.

    This proves the account-first lock prevents overselling the same
    inventory from concurrent trading operations.
    """

    session_factory = get_session_factory()

    with session_factory() as setup_session:
        account = _create_account(
            setup_session,
            initial_cash=Decimal("100000"),
        )

        account_id = account.account_id

        setup_session.add(
            PaperPositionModel(
                account_id=account_id,
                symbol="AAPL",
                quantity=10,
                average_cost=Decimal("200"),
                realized_pnl=Decimal("0"),
            )
        )

        setup_session.commit()

    worker_started = Event()

    with session_factory() as lock_session:
        locked_account = lock_session.scalar(
            select(PaperAccountModel)
            .where(
                PaperAccountModel.id
                == account_id
            )
            .with_for_update()
        )

        assert locked_account is not None

        locked_position = lock_session.scalar(
            select(PaperPositionModel)
            .where(
                PaperPositionModel.account_id
                == account_id,
                PaperPositionModel.symbol
                == "AAPL",
            )
            .with_for_update()
        )

        assert locked_position is not None

        # Transaction A consumes the complete position at bid=210.
        locked_account.cash_balance = Decimal("102100")
        locked_position.quantity = 0
        locked_position.realized_pnl = Decimal("100")

        def competing_sell() -> str:
            with session_factory() as worker_session:
                service = _build_service(
                    worker_session,
                    bid=Decimal("210"),
                    ask=Decimal("212"),
                )

                worker_started.set()

                with pytest.raises(
                    InsufficientPositionError
                ):
                    service.market_sell(
                        account_id=account_id,
                        symbol="AAPL",
                        quantity=10,
                    )

                return "rejected"

        with ThreadPoolExecutor(
            max_workers=1
        ) as executor:
            future = executor.submit(
                competing_sell
            )

            assert worker_started.wait(
                timeout=5
            )

            # B must still be waiting for A's account row lock.
            sleep(0.2)

            assert not future.done()

            # Commit A's latest account / inventory state and release
            # the locks.
            lock_session.commit()

            assert (
                future.result(
                    timeout=5
                )
                == "rejected"
            )

    with session_factory() as verification_session:
        persisted_account = verification_session.get(
            PaperAccountModel,
            account_id,
        )

        assert persisted_account is not None

        assert (
            persisted_account.cash_balance
            == Decimal("102100")
        )

        persisted_position = verification_session.scalar(
            select(PaperPositionModel)
            .where(
                PaperPositionModel.account_id
                == account_id,
                PaperPositionModel.symbol
                == "AAPL",
            )
        )

        assert persisted_position is not None

        assert persisted_position.quantity == 0

        assert (
            persisted_position.average_cost
            == Decimal("200")
        )

        assert (
            persisted_position.realized_pnl
            == Decimal("100")
        )

        # The competing SELL failed and therefore must not create any
        # additional order or execution.
        assert (
            _count_orders(
                verification_session,
                account_id=account_id,
            )
            == 0
        )

        assert (
            _count_executions(
                verification_session,
                account_id=account_id,
            )
            == 0
        )
