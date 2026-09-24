from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID, uuid4

from libs.trading.enums import OrderSide, OrderStatus, OrderType
from libs.trading.exceptions import (
    InsufficientBuyingPowerError,
    InsufficientPositionError,
)

ZERO = Decimal("0")


@dataclass(slots=True)
class PaperAccount:
    initial_cash: Decimal
    account_id: UUID | None = None
    cash_balance: Decimal | None = None

    def __post_init__(self) -> None:
        if self.initial_cash <= ZERO:
            raise ValueError("Initial cash must be greater than zero.")

        if self.account_id is None:
            self.account_id = uuid4()

        if self.cash_balance is None:
            self.cash_balance = self.initial_cash

        if self.cash_balance < ZERO:
            raise ValueError("Cash balance cannot be negative.")

    @property
    def buying_power(self) -> Decimal:
        return self.cash_balance

    def ensure_can_buy(
        self,
        *,
        quantity: int,
        estimated_price: Decimal,
    ) -> None:
        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")

        if estimated_price <= ZERO:
            raise ValueError(
                "Estimated price must be greater than zero."
            )

        required_cash = estimated_price * quantity

        if required_cash > self.buying_power:
            raise InsufficientBuyingPowerError(
                f"Required cash {required_cash} exceeds "
                f"buying power {self.buying_power}."
            )

    def debit(self, amount: Decimal) -> None:
        if amount <= ZERO:
            raise ValueError(
                "Debit amount must be greater than zero."
            )

        if amount > self.cash_balance:
            raise InsufficientBuyingPowerError(
                "Insufficient cash balance."
            )

        self.cash_balance -= amount

    def credit(self, amount: Decimal) -> None:
        if amount <= ZERO:
            raise ValueError(
                "Credit amount must be greater than zero."
            )

        self.cash_balance += amount


@dataclass(slots=True)
class Position:
    symbol: str
    quantity: int = 0
    average_cost: Decimal = ZERO
    realized_pnl: Decimal = ZERO

    def __post_init__(self) -> None:
        self.symbol = self.symbol.strip().upper()

        if not self.symbol:
            raise ValueError("Symbol must not be empty.")

        if self.quantity < 0:
            raise ValueError(
                "Position quantity cannot be negative."
            )

        if self.average_cost < ZERO:
            raise ValueError(
                "Average cost cannot be negative."
            )

    @property
    def is_open(self) -> bool:
        return self.quantity > 0

    def buy(
        self,
        *,
        quantity: int,
        price: Decimal,
    ) -> None:
        if quantity <= 0:
            raise ValueError(
                "Quantity must be greater than zero."
            )

        if price <= ZERO:
            raise ValueError(
                "Price must be greater than zero."
            )

        existing_cost = self.average_cost * self.quantity
        new_cost = price * quantity

        new_quantity = self.quantity + quantity

        self.average_cost = (
            existing_cost + new_cost
        ) / new_quantity

        self.quantity = new_quantity

    def sell(
        self,
        *,
        quantity: int,
        price: Decimal | None = None,
    ) -> None:
        if quantity <= 0:
            raise ValueError(
                "Quantity must be greater than zero."
            )

        if quantity > self.quantity:
            raise InsufficientPositionError(
                f"Cannot sell {quantity} shares; "
                f"only {self.quantity} available."
            )

        if price is not None:
            if price <= ZERO:
                raise ValueError(
                    "Price must be greater than zero."
                )

            self.realized_pnl += (
                price - self.average_cost
            ) * quantity

        self.quantity -= quantity

        if self.quantity == 0:
            self.average_cost = ZERO

    def market_value(
        self,
        mark_price: Decimal,
    ) -> Decimal:
        self._validate_mark_price(mark_price)

        return mark_price * self.quantity

    def unrealized_pnl(
        self,
        mark_price: Decimal,
    ) -> Decimal:
        self._validate_mark_price(mark_price)

        if not self.is_open:
            return ZERO

        return (
            mark_price - self.average_cost
        ) * self.quantity

    def _validate_mark_price(
        self,
        mark_price: Decimal,
    ) -> None:
        if mark_price <= ZERO:
            raise ValueError(
                "Mark price must be greater than zero."
            )


@dataclass(slots=True)
class PaperOrder:
    account_id: UUID
    symbol: str
    side: OrderSide
    quantity: int
    order_type: OrderType

    order_id: UUID | None = None
    status: OrderStatus = OrderStatus.NEW
    filled_quantity: int = 0

    limit_price: Decimal | None = None

    def __post_init__(self) -> None:
        if self.order_id is None:
            self.order_id = uuid4()

        self.symbol = self.symbol.strip().upper()

        if not self.symbol:
            raise ValueError("Symbol must not be empty.")

        if self.quantity <= 0:
            raise ValueError(
                "Quantity must be greater than zero."
            )

        if self.filled_quantity < 0:
            raise ValueError(
                "Filled quantity cannot be negative."
            )

        if self.filled_quantity > self.quantity:
            raise ValueError(
                "Filled quantity cannot exceed order quantity."
            )

        if self.order_type == OrderType.LIMIT:
            if self.limit_price is None:
                raise ValueError(
                    "Limit price is required for LIMIT orders."
                )

            if self.limit_price <= ZERO:
                raise ValueError(
                    "Limit price must be greater than zero."
                )

        if (
            self.order_type == OrderType.MARKET
            and self.limit_price is not None
        ):
            raise ValueError(
                "Market order must not define limit price."
            )

    @property
    def remaining_quantity(self) -> int:
        return self.quantity - self.filled_quantity

    def mark_pending(self) -> None:
        if self.status != OrderStatus.NEW:
            raise ValueError(
                "Only NEW orders can become PENDING."
            )

        self.status = OrderStatus.PENDING

    def record_fill(
        self,
        quantity: int,
    ) -> None:
        if quantity <= 0:
            raise ValueError(
                "Fill quantity must be greater than zero."
            )

        if quantity > self.remaining_quantity:
            raise ValueError(
                "Fill quantity exceeds remaining quantity."
            )

        self.filled_quantity += quantity

        if self.filled_quantity == self.quantity:
            self.status = OrderStatus.FILLED
        else:
            self.status = OrderStatus.PARTIALLY_FILLED

    def cancel(self) -> None:
        if self.status in {
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
        }:
            raise ValueError(
                f"Cannot cancel order in status {self.status}."
            )

        self.status = OrderStatus.CANCELLED

    def reject(self) -> None:
        if self.status == OrderStatus.FILLED:
            raise ValueError(
                "Filled order cannot be rejected."
            )

        self.status = OrderStatus.REJECTED