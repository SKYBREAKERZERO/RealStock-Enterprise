from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock

import pytest

from libs.trading.models import (
    PaperAccount,
    Position,
)
from services.trading.trading_portfolio_service import (
    TradingPortfolioService,
)


class StubPriceSource:
    def __init__(
        self,
        prices: dict[str, Decimal],
    ) -> None:
        self.prices = prices
        self.calls: list[list[str]] = []

    def get_prices(
        self,
        symbols: list[str],
    ) -> dict[str, Decimal]:
        self.calls.append(
            list(symbols)
        )

        return {
            symbol: self.prices[symbol]
            for symbol in symbols
            if symbol in self.prices
        }


def build_uow(
    *,
    account: PaperAccount | None,
    positions: list[Position] | None = None,
) -> Mock:
    uow = Mock()

    uow.__enter__ = Mock(
        return_value=uow
    )

    uow.__exit__ = Mock(
        return_value=None
    )

    (
        uow.paper_accounts
        .get_by_user_id
        .return_value
    ) = account

    (
        uow.paper_positions
        .list_by_account
        .return_value
    ) = (
        positions
        if positions is not None
        else []
    )

    return uow


def test_snapshot_values_single_open_position() -> None:
    account = PaperAccount(
        initial_cash=Decimal("100000"),
        cash_balance=Decimal("98000"),
    )

    positions = [
        Position(
            symbol="AAPL",
            quantity=10,
            average_cost=Decimal("200"),
        )
    ]

    price_source = StubPriceSource(
        {
            "AAPL": Decimal("210"),
        }
    )

    uow = build_uow(
        account=account,
        positions=positions,
    )

    service = TradingPortfolioService(
        unit_of_work=uow,
        price_source=price_source,
    )

    snapshot = service.get_snapshot(
        user_id="user-001",
    )

    assert snapshot.account_id == account.account_id
    assert snapshot.initial_cash == Decimal("100000")
    assert snapshot.cash_balance == Decimal("98000")

    assert snapshot.total_cost_basis == Decimal("2000")
    assert snapshot.market_value == Decimal("2100")
    assert snapshot.equity == Decimal("100100")

    assert snapshot.realized_pnl == Decimal("0")
    assert snapshot.unrealized_pnl == Decimal("100")
    assert snapshot.total_pnl == Decimal("100")

    assert len(snapshot.positions) == 1

    valuation = snapshot.positions[0]

    assert valuation.symbol == "AAPL"
    assert valuation.quantity == 10
    assert valuation.average_cost == Decimal("200")
    assert valuation.mark_price == Decimal("210")
    assert valuation.cost_basis == Decimal("2000")
    assert valuation.market_value == Decimal("2100")
    assert valuation.realized_pnl == Decimal("0")
    assert valuation.unrealized_pnl == Decimal("100")
    assert valuation.total_pnl == Decimal("100")

    assert price_source.calls == [
        [
            "AAPL",
        ]
    ]

    (
        uow.paper_accounts
        .get_by_user_id
        .assert_called_once_with(
            "user-001"
        )
    )

    (
        uow.paper_positions
        .list_by_account
        .assert_called_once_with(
            account.account_id
        )
    )

    (
        uow.paper_accounts
        .get_for_update
        .assert_not_called()
    )

    (
        uow.paper_positions
        .get_for_update
        .assert_not_called()
    )

    uow.commit.assert_not_called()


def test_snapshot_supports_multiple_positions() -> None:
    account = PaperAccount(
        initial_cash=Decimal("100000"),
        cash_balance=Decimal("95950"),
    )

    positions = [
        Position(
            symbol="AAPL",
            quantity=10,
            average_cost=Decimal("200"),
        ),
        Position(
            symbol="MSFT",
            quantity=5,
            average_cost=Decimal("410"),
        ),
    ]

    price_source = StubPriceSource(
        {
            "AAPL": Decimal("210"),
            "MSFT": Decimal("420"),
        }
    )

    service = TradingPortfolioService(
        unit_of_work=build_uow(
            account=account,
            positions=positions,
        ),
        price_source=price_source,
    )

    snapshot = service.get_snapshot(
        user_id="user-001",
    )

    assert snapshot.total_cost_basis == Decimal("4050")
    assert snapshot.market_value == Decimal("4200")
    assert snapshot.equity == Decimal("100150")
    assert snapshot.unrealized_pnl == Decimal("150")
    assert snapshot.realized_pnl == Decimal("0")
    assert snapshot.total_pnl == Decimal("150")

    assert [
        valuation.symbol
        for valuation in snapshot.positions
    ] == [
        "AAPL",
        "MSFT",
    ]

    assert price_source.calls == [
        [
            "AAPL",
            "MSFT",
        ]
    ]


def test_snapshot_includes_realized_pnl_from_closed_position() -> None:
    account = PaperAccount(
        initial_cash=Decimal("100000"),
        cash_balance=Decimal("100125"),
    )

    closed_position = Position(
        symbol="AAPL",
        quantity=0,
        average_cost=Decimal("0"),
        realized_pnl=Decimal("125"),
    )

    price_source = StubPriceSource(
        {}
    )

    service = TradingPortfolioService(
        unit_of_work=build_uow(
            account=account,
            positions=[
                closed_position,
            ],
        ),
        price_source=price_source,
    )

    snapshot = service.get_snapshot(
        user_id="user-001",
    )

    assert snapshot.total_cost_basis == Decimal("0")
    assert snapshot.market_value == Decimal("0")
    assert snapshot.equity == Decimal("100125")

    assert snapshot.realized_pnl == Decimal("125")
    assert snapshot.unrealized_pnl == Decimal("0")
    assert snapshot.total_pnl == Decimal("125")

    valuation = snapshot.positions[0]

    assert valuation.mark_price is None
    assert valuation.cost_basis == Decimal("0")
    assert valuation.market_value == Decimal("0")
    assert valuation.realized_pnl == Decimal("125")
    assert valuation.unrealized_pnl == Decimal("0")
    assert valuation.total_pnl == Decimal("125")

    assert price_source.calls == []


def test_snapshot_requests_prices_only_for_open_positions() -> None:
    account = PaperAccount(
        initial_cash=Decimal("100000"),
        cash_balance=Decimal("98050"),
    )

    positions = [
        Position(
            symbol="AAPL",
            quantity=10,
            average_cost=Decimal("200"),
        ),
        Position(
            symbol="MSFT",
            quantity=0,
            average_cost=Decimal("0"),
            realized_pnl=Decimal("50"),
        ),
    ]

    price_source = StubPriceSource(
        {
            "AAPL": Decimal("210"),
        }
    )

    service = TradingPortfolioService(
        unit_of_work=build_uow(
            account=account,
            positions=positions,
        ),
        price_source=price_source,
    )

    snapshot = service.get_snapshot(
        user_id="user-001",
    )

    assert price_source.calls == [
        [
            "AAPL",
        ]
    ]

    assert snapshot.realized_pnl == Decimal("50")
    assert snapshot.unrealized_pnl == Decimal("100")
    assert snapshot.total_pnl == Decimal("150")


def test_snapshot_rejects_missing_market_price() -> None:
    account = PaperAccount(
        initial_cash=Decimal("100000"),
        cash_balance=Decimal("98000"),
    )

    service = TradingPortfolioService(
        unit_of_work=build_uow(
            account=account,
            positions=[
                Position(
                    symbol="AAPL",
                    quantity=10,
                    average_cost=Decimal("200"),
                )
            ],
        ),
        price_source=StubPriceSource(
            {}
        ),
    )

    with pytest.raises(
        ValueError,
        match="Missing market price for AAPL",
    ):
        service.get_snapshot(
            user_id="user-001",
        )


def test_snapshot_rejects_missing_account_before_price_lookup() -> None:
    price_source = StubPriceSource(
        {
            "AAPL": Decimal("210"),
        }
    )

    uow = build_uow(
        account=None,
    )

    service = TradingPortfolioService(
        unit_of_work=uow,
        price_source=price_source,
    )

    with pytest.raises(
        ValueError,
        match="Paper account for user",
    ):
        service.get_snapshot(
            user_id="missing-user",
        )

    assert price_source.calls == []

    (
        uow.paper_positions
        .list_by_account
        .assert_not_called()
    )

    uow.commit.assert_not_called()
