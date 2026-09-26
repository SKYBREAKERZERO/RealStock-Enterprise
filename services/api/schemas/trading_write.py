from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from libs.trading.execution import Execution
from services.api.schemas.trading import (
    PaperExecutionResponse,
    PaperOrderResponse,
)
from services.trading.models import TradeExecutionResult


class MarketOrderRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    symbol: str = Field(min_length=1, max_length=32)
    quantity: int = Field(gt=0)


class LimitOrderRequest(MarketOrderRequest):
    limit_price: Decimal = Field(gt=Decimal("0"))


class TradeExecutionResponse(BaseModel):
    order: PaperOrderResponse
    execution: PaperExecutionResponse

    @classmethod
    def from_domain(
        cls,
        result: TradeExecutionResult,
    ) -> TradeExecutionResponse:
        return cls(
            order=PaperOrderResponse.from_domain(result.order),
            execution=PaperExecutionResponse.from_domain(
                result.execution
            ),
        )


class LimitOrderProcessResponse(BaseModel):
    order_id: UUID
    executed: bool
    execution: PaperExecutionResponse | None

    @classmethod
    def from_domain(
        cls,
        *,
        order_id: UUID,
        execution: Execution | None,
    ) -> LimitOrderProcessResponse:
        return cls(
            order_id=order_id,
            executed=execution is not None,
            execution=(
                PaperExecutionResponse.from_domain(execution)
                if execution is not None
                else None
            ),
        )


class CreatePaperAccountRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    initial_cash: Decimal = Field(
        default=Decimal("100000"),
        gt=Decimal("0"),
    )

