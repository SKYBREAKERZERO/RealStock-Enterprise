from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from libs.database.unit_of_work import UnitOfWork
from libs.trading.models import (
    PaperAccount,
    Position,
)
from libs.trading.portfolio import (
    PortfolioCalculator,
)

ZERO = Decimal("0")


class TradingPortfolioAccountNotFoundError(
    ValueError
):
    pass


class TradingPortfolioValuationUnavailableError(
    ValueError
):
    pass


class TradingValuationPriceSource(Protocol):
    """
    Explicit valuation-price boundary for paper-trading portfolios.

    Implementations return valuation prices keyed by normalized
    market symbol.

    The source decides what the valuation price means. For example:

    - Redis bid/ask midpoint for the legacy local path.
    - Twelve Data snapshot close for the OHLC snapshot path.

    OHLC close must never be converted into synthetic bid/ask data.
    """

    def get_prices(
        self,
        symbols: list[str],
    ) -> Mapping[str, Decimal]:
        ...


@dataclass(frozen=True, slots=True)
class TradingPositionValuation:
    symbol: str
    quantity: int
    average_cost: Decimal

    mark_price: Decimal | None
    cost_basis: Decimal
    market_value: Decimal

    realized_pnl: Decimal
    unrealized_pnl: Decimal

    @property
    def total_pnl(
        self,
    ) -> Decimal:
        return (
            self.realized_pnl
            + self.unrealized_pnl
        )


@dataclass(frozen=True, slots=True)
class TradingPortfolioSnapshot:
    account_id: UUID

    initial_cash: Decimal
    cash_balance: Decimal

    total_cost_basis: Decimal
    market_value: Decimal
    equity: Decimal

    realized_pnl: Decimal
    unrealized_pnl: Decimal

    positions: tuple[
        TradingPositionValuation,
        ...,
    ]

    @property
    def total_pnl(
        self,
    ) -> Decimal:
        return (
            self.realized_pnl
            + self.unrealized_pnl
        )


@dataclass(slots=True)
class TradingPortfolioService:
    """
    Build a read-only valuation snapshot for one paper account.

    Database work is completed before valuation-price I/O starts.
    This avoids holding a database transaction while Redis or an
    upstream market-data provider is being queried.
    """

    unit_of_work: UnitOfWork
    price_source: TradingValuationPriceSource
    calculator: PortfolioCalculator = field(
        default_factory=PortfolioCalculator,
    )

    def get_snapshot(
        self,
        *,
        user_id: str,
    ) -> TradingPortfolioSnapshot:
        account, positions = (
            self._load_account_state(
                user_id=user_id,
            )
        )

        open_symbols = [
            position.symbol
            for position in positions
            if position.is_open
        ]

        market_prices: Mapping[
            str,
            Decimal,
        ]

        if open_symbols:
            market_prices = (
                self.price_source
                .get_prices(
                    open_symbols
                )
            )
        else:
            market_prices = {}

        self._validate_market_prices(
            symbols=open_symbols,
            market_prices=market_prices,
        )

        aggregate = self.calculator.calculate(
            account=account,
            positions=positions,
            market_prices=market_prices,
        )

        position_valuations = tuple(
            self._value_position(
                position=position,
                market_prices=market_prices,
            )
            for position in positions
        )

        total_cost_basis = sum(
            (
                valuation.cost_basis
                for valuation
                in position_valuations
            ),
            ZERO,
        )

        account_id = account.account_id

        if account_id is None:
            raise RuntimeError(
                "Persisted paper account must have "
                "an account_id."
            )

        return TradingPortfolioSnapshot(
            account_id=account_id,
            initial_cash=account.initial_cash,
            cash_balance=aggregate.cash_balance,
            total_cost_basis=total_cost_basis,
            market_value=aggregate.market_value,
            equity=aggregate.equity,
            realized_pnl=aggregate.realized_pnl,
            unrealized_pnl=aggregate.unrealized_pnl,
            positions=position_valuations,
        )

    def _load_account_state(
        self,
        *,
        user_id: str,
    ) -> tuple[
        PaperAccount,
        list[Position],
    ]:
        with self.unit_of_work:
            account = (
                self.unit_of_work
                .paper_accounts
                .get_by_user_id(
                    user_id
                )
            )

            if account is None:
                raise (
                    TradingPortfolioAccountNotFoundError(
                        "Paper account for user "
                        f"{user_id!r} not found."
                    )
                )

            account_id = account.account_id

            if account_id is None:
                raise RuntimeError(
                    "Persisted paper account must have "
                    "an account_id."
                )

            positions = (
                self.unit_of_work
                .paper_positions
                .list_by_account(
                    account_id
                )
            )

            return (
                account,
                positions,
            )

    @staticmethod
    def _validate_market_prices(
        *,
        symbols: list[str],
        market_prices: Mapping[
            str,
            Decimal,
        ],
    ) -> None:
        for symbol in symbols:
            price = market_prices.get(
                symbol
            )

            if price is None:
                raise (
                    TradingPortfolioValuationUnavailableError(
                        "Missing market price for "
                        f"{symbol}."
                    )
                )

            if price <= ZERO:
                raise (
                    TradingPortfolioValuationUnavailableError(
                        "Invalid market price for "
                        f"{symbol}: {price}."
                    )
                )

    @staticmethod
    def _value_position(
        *,
        position: Position,
        market_prices: Mapping[
            str,
            Decimal,
        ],
    ) -> TradingPositionValuation:
        if not position.is_open:
            return TradingPositionValuation(
                symbol=position.symbol,
                quantity=position.quantity,
                average_cost=position.average_cost,
                mark_price=None,
                cost_basis=ZERO,
                market_value=ZERO,
                realized_pnl=position.realized_pnl,
                unrealized_pnl=ZERO,
            )

        mark_price = market_prices[
            position.symbol
        ]

        cost_basis = (
            position.average_cost
            * position.quantity
        )

        market_value = (
            position.market_value(
                mark_price
            )
        )

        unrealized_pnl = (
            position.unrealized_pnl(
                mark_price
            )
        )

        return TradingPositionValuation(
            symbol=position.symbol,
            quantity=position.quantity,
            average_cost=position.average_cost,
            mark_price=mark_price,
            cost_basis=cost_basis,
            market_value=market_value,
            realized_pnl=position.realized_pnl,
            unrealized_pnl=unrealized_pnl,
        )
