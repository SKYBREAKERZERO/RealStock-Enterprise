from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal

from libs.trading.models import PaperAccount, Position

ZERO = Decimal("0")


@dataclass(frozen=True, slots=True)
class PortfolioSnapshot:
    cash_balance: Decimal
    market_value: Decimal
    equity: Decimal
    unrealized_pnl: Decimal
    realized_pnl: Decimal


class PortfolioCalculator:
    def calculate(
        self,
        *,
        account: PaperAccount,
        positions: list[Position],
        market_prices: Mapping[str, Decimal],
    ) -> PortfolioSnapshot:
        total_market_value = ZERO
        total_unrealized_pnl = ZERO
        total_realized_pnl = ZERO

        for position in positions:
            total_realized_pnl += position.realized_pnl

            if not position.is_open:
                continue

            try:
                mark_price = market_prices[position.symbol]
            except KeyError as exc:
                raise ValueError(
                    f"Missing market price for {position.symbol}."
                ) from exc

            total_market_value += position.market_value(
                mark_price
            )

            total_unrealized_pnl += (
                position.unrealized_pnl(
                    mark_price
                )
            )

        equity = (
            account.cash_balance
            + total_market_value
        )

        return PortfolioSnapshot(
            cash_balance=account.cash_balance,
            market_value=total_market_value,
            equity=equity,
            unrealized_pnl=total_unrealized_pnl,
            realized_pnl=total_realized_pnl,
        )