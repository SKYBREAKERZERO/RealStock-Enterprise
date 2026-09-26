from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from libs.trading.enums import (
    OrderSide,
    OrderStatus,
    OrderType,
)
from libs.trading.execution import Execution
from libs.trading.models import (
    PaperAccount,
    PaperOrder,
    Position,
)
from services.trading.trading_portfolio_service import (
    TradingPortfolioSnapshot,
    TradingPositionValuation,
)


class PaperAccountResponse(BaseModel):
    account_id: UUID
    initial_cash: Decimal
    cash_balance: Decimal

    @classmethod
    def from_domain(
        cls,
        account: PaperAccount,
    ) -> PaperAccountResponse:
        return cls(
            account_id=account.account_id,
            initial_cash=account.initial_cash,
            cash_balance=account.cash_balance,
        )


class PaperPositionResponse(BaseModel):
    symbol: str
    quantity: int
    average_cost: Decimal
    realized_pnl: Decimal

    @classmethod
    def from_domain(
        cls,
        position: Position,
    ) -> PaperPositionResponse:
        return cls(
            symbol=position.symbol,
            quantity=position.quantity,
            average_cost=position.average_cost,
            realized_pnl=position.realized_pnl,
        )


class PaperOrderResponse(BaseModel):
    order_id: UUID
    account_id: UUID
    symbol: str
    side: OrderSide
    quantity: int
    order_type: OrderType
    status: OrderStatus
    filled_quantity: int
    limit_price: Decimal | None

    @classmethod
    def from_domain(
        cls,
        order: PaperOrder,
    ) -> PaperOrderResponse:
        return cls(
            order_id=order.order_id,
            account_id=order.account_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            order_type=order.order_type,
            status=order.status,
            filled_quantity=order.filled_quantity,
            limit_price=order.limit_price,
        )


class PaperExecutionResponse(BaseModel):
    execution_id: UUID
    order_id: UUID
    symbol: str
    side: OrderSide
    quantity: int
    price: Decimal

    @classmethod
    def from_domain(
        cls,
        execution: Execution,
    ) -> PaperExecutionResponse:
        return cls(
            execution_id=execution.execution_id,
            order_id=execution.order_id,
            symbol=execution.symbol,
            side=execution.side,
            quantity=execution.quantity,
            price=execution.price,
        )


class TradingPositionValuationResponse(BaseModel):
    symbol: str
    quantity: int
    average_cost: Decimal

    mark_price: Decimal | None
    cost_basis: Decimal
    market_value: Decimal

    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_pnl: Decimal

    @classmethod
    def from_domain(
        cls,
        valuation: TradingPositionValuation,
    ) -> TradingPositionValuationResponse:
        return cls(
            symbol=valuation.symbol,
            quantity=valuation.quantity,
            average_cost=valuation.average_cost,
            mark_price=valuation.mark_price,
            cost_basis=valuation.cost_basis,
            market_value=valuation.market_value,
            realized_pnl=valuation.realized_pnl,
            unrealized_pnl=valuation.unrealized_pnl,
            total_pnl=valuation.total_pnl,
        )


class TradingPortfolioResponse(BaseModel):
    account_id: UUID

    initial_cash: Decimal
    cash_balance: Decimal

    total_cost_basis: Decimal
    market_value: Decimal
    equity: Decimal

    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_pnl: Decimal

    positions: list[TradingPositionValuationResponse]

    @classmethod
    def from_domain(
        cls,
        snapshot: TradingPortfolioSnapshot,
    ) -> TradingPortfolioResponse:
        return cls(
            account_id=snapshot.account_id,
            initial_cash=snapshot.initial_cash,
            cash_balance=snapshot.cash_balance,
            total_cost_basis=snapshot.total_cost_basis,
            market_value=snapshot.market_value,
            equity=snapshot.equity,
            realized_pnl=snapshot.realized_pnl,
            unrealized_pnl=snapshot.unrealized_pnl,
            total_pnl=snapshot.total_pnl,
            positions=[
                TradingPositionValuationResponse.from_domain(
                    position
                )
                for position in snapshot.positions
            ],
        )
