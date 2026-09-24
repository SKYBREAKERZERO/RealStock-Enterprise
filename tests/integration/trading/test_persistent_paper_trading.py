from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import delete, select

from libs.database.models import (
    PaperAccountModel,
    PaperExecutionModel,
    PaperOrderModel,
    PaperPositionModel,
)
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


@pytest.fixture
def session():
    session_factory = get_session_factory()
    db_session = session_factory()

    try:
        yield db_session
    finally:
        db_session.rollback()

        db_session.execute(
            delete(PaperExecutionModel),
        )
        db_session.execute(
            delete(PaperOrderModel),
        )
        db_session.execute(
            delete(PaperPositionModel),
        )
        db_session.execute(
            delete(PaperAccountModel),
        )

        db_session.commit()
        db_session.close()


def _build_service(
    session,
) -> PersistentPaperTradingService:
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

    broker = PaperBroker()

    trading_service = PaperTradingService(
        broker=broker,
        quote_service=quote_service,
    )

    unit_of_work = SqlAlchemyUnitOfWork(
        session=session,
    )

    return PersistentPaperTradingService(
        trading_service=trading_service,
        unit_of_work=unit_of_work,
    )


def _create_account(
    session,
    *,
    initial_cash: Decimal = Decimal("100000"),
) -> PaperAccount:
    account = PaperAccount(
        initial_cash=initial_cash,
    )

    assert account.account_id is not None

    model = PaperAccountModel(
        id=account.account_id,
        user_id=f"integration-user-{uuid4()}",
        initial_cash=account.initial_cash,
        cash_balance=account.cash_balance,
        currency="USD",
    )

    session.add(model)
    session.commit()

    return account


def test_market_buy_persists_complete_trade(
    session,
) -> None:
    account = _create_account(session)

    assert account.account_id is not None

    service = _build_service(session)

    result = service.market_buy(
        account_id=account.account_id,
        symbol="AAPL",
        quantity=10,
    )

    session.expire_all()

    account_model = session.get(
        PaperAccountModel,
        account.account_id,
    )

    position_model = session.scalar(
        select(PaperPositionModel).where(
            PaperPositionModel.account_id
            == account.account_id,
            PaperPositionModel.symbol
            == "AAPL",
        ),
    )

    order_model = session.get(
        PaperOrderModel,
        result.order.order_id,
    )

    execution_model = session.get(
        PaperExecutionModel,
        result.execution.execution_id,
    )

    assert account_model is not None
    assert (
        account_model.cash_balance
        == Decimal("97880.000000")
    )

    assert position_model is not None
    assert position_model.quantity == 10
    assert (
        position_model.average_cost
        == Decimal("212.000000")
    )

    assert order_model is not None
    assert order_model.status == "FILLED"
    assert order_model.filled_quantity == 10
    assert order_model.quantity == 10

    assert execution_model is not None
    assert execution_model.symbol == "AAPL"
    assert execution_model.quantity == 10
    assert (
        execution_model.price
        == Decimal("212.000000")
    )


def test_market_buy_updates_existing_position(
    session,
) -> None:
    account = _create_account(session)

    assert account.account_id is not None

    position_model = PaperPositionModel(
        account_id=account.account_id,
        symbol="AAPL",
        quantity=5,
        average_cost=Decimal("200"),
        realized_pnl=Decimal("0"),
    )

    session.add(position_model)
    session.commit()

    service = _build_service(session)

    service.market_buy(
        account_id=account.account_id,
        symbol="AAPL",
        quantity=5,
    )

    session.expire_all()

    refreshed_account = session.get(
        PaperAccountModel,
        account.account_id,
    )

    refreshed_position = session.scalar(
        select(PaperPositionModel).where(
            PaperPositionModel.account_id
            == account.account_id,
            PaperPositionModel.symbol
            == "AAPL",
        ),
    )

    assert refreshed_account is not None
    assert (
        refreshed_account.cash_balance
        == Decimal("98940.000000")
    )

    assert refreshed_position is not None
    assert refreshed_position.quantity == 10
    assert (
        refreshed_position.average_cost
        == Decimal("206.000000")
    )


def test_market_sell_persists_realized_profit(
    session,
) -> None:
    account = _create_account(session)

    assert account.account_id is not None

    position_model = PaperPositionModel(
        account_id=account.account_id,
        symbol="AAPL",
        quantity=10,
        average_cost=Decimal("200"),
        realized_pnl=Decimal("0"),
    )

    session.add(position_model)
    session.commit()

    service = _build_service(session)

    result = service.market_sell(
        account_id=account.account_id,
        symbol="AAPL",
        quantity=10,
    )

    session.expire_all()

    refreshed_account = session.get(
        PaperAccountModel,
        account.account_id,
    )

    refreshed_position = session.scalar(
        select(PaperPositionModel).where(
            PaperPositionModel.account_id
            == account.account_id,
            PaperPositionModel.symbol
            == "AAPL",
        ),
    )

    order_model = session.get(
        PaperOrderModel,
        result.order.order_id,
    )

    execution_model = session.get(
        PaperExecutionModel,
        result.execution.execution_id,
    )

    assert refreshed_account is not None
    assert (
        refreshed_account.cash_balance
        == Decimal("102100.000000")
    )

    assert refreshed_position is not None
    assert refreshed_position.quantity == 0
    assert (
        refreshed_position.realized_pnl
        == Decimal("100.000000")
    )

    assert order_model is not None
    assert order_model.status == "FILLED"
    assert order_model.filled_quantity == 10

    assert execution_model is not None
    assert execution_model.side == "SELL"
    assert execution_model.quantity == 10
    assert (
        execution_model.price
        == Decimal("210.000000")
    )


def test_insufficient_buying_power_rolls_back_all_writes(
    session,
) -> None:
    account = _create_account(
        session,
        initial_cash=Decimal("100"),
    )

    assert account.account_id is not None

    service = _build_service(session)

    with pytest.raises(
        InsufficientBuyingPowerError,
    ):
        service.market_buy(
            account_id=account.account_id,
            symbol="AAPL",
            quantity=1,
        )

    session.expire_all()

    orders = session.scalars(
        select(PaperOrderModel).where(
            PaperOrderModel.account_id
            == account.account_id,
        ),
    ).all()

    executions = session.scalars(
        select(PaperExecutionModel).where(
            PaperExecutionModel.account_id
            == account.account_id,
        ),
    ).all()

    positions = session.scalars(
        select(PaperPositionModel).where(
            PaperPositionModel.account_id
            == account.account_id,
        ),
    ).all()

    account_model = session.get(
        PaperAccountModel,
        account.account_id,
    )

    assert orders == []
    assert executions == []
    assert positions == []

    assert account_model is not None
    assert (
        account_model.cash_balance
        == Decimal("100.000000")
    )


def test_sell_without_position_rolls_back_all_writes(
    session,
) -> None:
    account = _create_account(session)

    assert account.account_id is not None

    service = _build_service(session)

    with pytest.raises(
        InsufficientPositionError,
    ):
        service.market_sell(
            account_id=account.account_id,
            symbol="AAPL",
            quantity=1,
        )

    session.expire_all()

    orders = session.scalars(
        select(PaperOrderModel).where(
            PaperOrderModel.account_id
            == account.account_id,
        ),
    ).all()

    executions = session.scalars(
        select(PaperExecutionModel).where(
            PaperExecutionModel.account_id
            == account.account_id,
        ),
    ).all()

    positions = session.scalars(
        select(PaperPositionModel).where(
            PaperPositionModel.account_id
            == account.account_id,
        ),
    ).all()

    account_model = session.get(
        PaperAccountModel,
        account.account_id,
    )

    assert orders == []
    assert executions == []
    assert positions == []

    assert account_model is not None
    assert (
        account_model.cash_balance
        == Decimal("100000.000000")
    )