from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID, uuid4

from libs.trading.enums import OrderSide


@dataclass(frozen=True, slots=True)
class Execution:
    order_id: UUID
    symbol: str
    side: OrderSide
    quantity: int
    price: Decimal
    execution_id: UUID | None = None

    def __post_init__(self) -> None:
        if self.execution_id is None:
            object.__setattr__(
                self,
                "execution_id",
                uuid4(),
            )

        if self.quantity <= 0:
            raise ValueError(
                "Execution quantity must be greater than zero."
            )

        if self.price <= Decimal("0"):
            raise ValueError(
                "Execution price must be greater than zero."
            )