from __future__ import annotations

from datetime import (
    UTC,
    datetime,
)
from decimal import Decimal
from enum import StrEnum
from uuid import (
    UUID,
    uuid4,
)

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

from libs.domain.market import Market


class RiskSeverity(StrEnum):
    """
    Severity of a detected risk condition.
    """

    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class RiskType(StrEnum):
    """
    Canonical risk categories used by RealStock.
    """

    PRICE_MOVE_PERCENT = (
        "PRICE_MOVE_PERCENT"
    )

    SPREAD_PERCENT = (
        "SPREAD_PERCENT"
    )

    POSITION_EXPOSURE = (
        "POSITION_EXPOSURE"
    )

    UNREALIZED_LOSS_PERCENT = (
        "UNREALIZED_LOSS_PERCENT"
    )


class RiskAlert(BaseModel):
    """
    Immutable domain representation of one detected
    risk condition.

    Infrastructure concerns such as EventBridge, SQS,
    SNS, persistence, or HTTP do not belong here.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    alert_id: UUID = Field(
        default_factory=uuid4,
    )

    risk_type: RiskType
    severity: RiskSeverity

    market: Market
    symbol: str

    observed_value: Decimal

    threshold: Decimal = Field(
        gt=Decimal("0"),
    )

    message: str = Field(
        min_length=1,
        max_length=512,
    )

    occurred_at: datetime = Field(
        default_factory=lambda: datetime.now(
            UTC
        ),
    )

    @field_validator("symbol")
    @classmethod
    def validate_symbol(
        cls,
        value: str,
    ) -> str:
        symbol = value.strip().upper()

        if not symbol:
            raise ValueError(
                "symbol must not be empty"
            )

        if len(symbol) > 32:
            raise ValueError(
                "symbol must not exceed "
                "32 characters"
            )

        return symbol

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(
        cls,
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None:
            raise ValueError(
                "occurred_at must be "
                "timezone-aware"
            )

        return value.astimezone(
            UTC
        )