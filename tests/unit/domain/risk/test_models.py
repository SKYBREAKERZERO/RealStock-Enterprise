from __future__ import annotations

from datetime import (
    UTC,
    datetime,
)
from decimal import Decimal

import pytest
from pydantic import ValidationError

from libs.domain.market import Market
from libs.domain.risk import (
    RiskAlert,
    RiskSeverity,
    RiskType,
)

pytestmark = pytest.mark.unit


def test_risk_alert_can_be_created() -> None:
    alert = RiskAlert(
        risk_type=(
            RiskType.PRICE_MOVE_PERCENT
        ),
        severity=(
            RiskSeverity.WARNING
        ),
        market=Market.US,
        symbol="AAPL",
        observed_value=Decimal("2.5"),
        threshold=Decimal("2"),
        message="Price move detected",
        occurred_at=datetime(
            2026,
            9,
            6,
            1,
            0,
            tzinfo=UTC,
        ),
    )

    assert alert.symbol == "AAPL"

    assert (
        alert.risk_type
        == RiskType.PRICE_MOVE_PERCENT
    )

    assert (
        alert.severity
        == RiskSeverity.WARNING
    )


def test_risk_alert_normalizes_symbol() -> None:
    alert = RiskAlert(
        risk_type=(
            RiskType.PRICE_MOVE_PERCENT
        ),
        severity=(
            RiskSeverity.WARNING
        ),
        market=Market.US,
        symbol="  aapl ",
        observed_value=Decimal("2"),
        threshold=Decimal("2"),
        message="risk",
    )

    assert alert.symbol == "AAPL"


def test_risk_alert_rejects_zero_threshold() -> None:
    with pytest.raises(
        ValidationError
    ):
        RiskAlert(
            risk_type=(
                RiskType.PRICE_MOVE_PERCENT
            ),
            severity=(
                RiskSeverity.WARNING
            ),
            market=Market.US,
            symbol="AAPL",
            observed_value=Decimal("2"),
            threshold=Decimal("0"),
            message="risk",
        )


def test_risk_alert_rejects_naive_timestamp() -> None:
    with pytest.raises(
        ValidationError
    ):
        RiskAlert(
            risk_type=(
                RiskType.PRICE_MOVE_PERCENT
            ),
            severity=(
                RiskSeverity.WARNING
            ),
            market=Market.US,
            symbol="AAPL",
            observed_value=Decimal("2"),
            threshold=Decimal("2"),
            message="risk",
            occurred_at=datetime(
                2026,
                9,
                6,
                1,
                0,
            ),
        )