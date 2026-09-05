from __future__ import annotations

from datetime import (
    UTC,
    datetime,
    timedelta,
)
from decimal import Decimal

import pytest

from libs.domain.market import (
    Market,
    MarketQuote,
)
from libs.domain.risk import (
    PriceMoveRule,
    RiskSeverity,
    RiskType,
)

pytestmark = pytest.mark.unit


BASE_TIMESTAMP = datetime(
    2026,
    9,
    6,
    1,
    0,
    tzinfo=UTC,
)


def build_quote(
    *,
    price: Decimal,
    symbol: str = "AAPL",
    market: Market = Market.US,
    seconds: int = 0,
) -> MarketQuote:
    return MarketQuote(
        symbol=symbol,
        market=market,
        bid_price=price,
        ask_price=price,
        bid_size=100,
        ask_size=100,
        timestamp=(
            BASE_TIMESTAMP
            + timedelta(seconds=seconds)
        ),
    )


def test_no_alert_below_warning_threshold() -> None:
    rule = PriceMoveRule()

    alert = rule.evaluate(
        previous_quote=build_quote(
            price=Decimal("100"),
        ),
        current_quote=build_quote(
            price=Decimal("101"),
            seconds=1,
        ),
    )

    assert alert is None


def test_warning_alert_at_warning_threshold() -> None:
    rule = PriceMoveRule()

    alert = rule.evaluate(
        previous_quote=build_quote(
            price=Decimal("100"),
        ),
        current_quote=build_quote(
            price=Decimal("102"),
            seconds=1,
        ),
    )

    assert alert is not None

    assert (
        alert.severity
        == RiskSeverity.WARNING
    )

    assert (
        alert.risk_type
        == RiskType.PRICE_MOVE_PERCENT
    )

    assert (
        alert.observed_value
        == Decimal("2")
    )

    assert (
        alert.threshold
        == Decimal("2")
    )


def test_critical_alert_at_critical_threshold() -> None:
    rule = PriceMoveRule()

    alert = rule.evaluate(
        previous_quote=build_quote(
            price=Decimal("100"),
        ),
        current_quote=build_quote(
            price=Decimal("105"),
            seconds=1,
        ),
    )

    assert alert is not None

    assert (
        alert.severity
        == RiskSeverity.CRITICAL
    )

    assert (
        alert.observed_value
        == Decimal("5")
    )

    assert (
        alert.threshold
        == Decimal("5")
    )


def test_negative_move_preserves_direction() -> None:
    rule = PriceMoveRule()

    alert = rule.evaluate(
        previous_quote=build_quote(
            price=Decimal("100"),
        ),
        current_quote=build_quote(
            price=Decimal("94"),
            seconds=1,
        ),
    )

    assert alert is not None

    assert (
        alert.severity
        == RiskSeverity.CRITICAL
    )

    assert (
        alert.observed_value
        == Decimal("-6")
    )


def test_rejects_different_symbols() -> None:
    rule = PriceMoveRule()

    with pytest.raises(
        ValueError,
        match="same instrument",
    ):
        rule.evaluate(
            previous_quote=build_quote(
                price=Decimal("100"),
                symbol="AAPL",
            ),
            current_quote=build_quote(
                price=Decimal("105"),
                symbol="MSFT",
                seconds=1,
            ),
        )


def test_rejects_invalid_threshold_order() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "critical threshold must be "
            "greater"
        ),
    ):
        PriceMoveRule(
            warning_threshold_percent=(
                Decimal("5")
            ),
            critical_threshold_percent=(
                Decimal("2")
            ),
        )