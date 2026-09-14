from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from pydantic import ValidationError

from libs.domain.market import Market
from libs.domain.portfolio import (
    Currency,
    Portfolio,
    Position,
)

pytestmark = pytest.mark.unit


# ============================================================
# Helpers
# ============================================================


def build_position(
    **overrides: object,
) -> Position:
    data: dict[str, object] = {
        "symbol": "AAPL",
        "market": Market.US,
        "quantity": Decimal("100"),
        "average_cost": Decimal("200.50"),
    }

    data.update(overrides)

    return Position(**data)


def build_portfolio(
    **overrides: object,
) -> Portfolio:
    data: dict[str, object] = {
        "user_id": "user-001",
        "name": "Growth Portfolio",
        "currency": Currency.USD,
    }

    data.update(overrides)

    return Portfolio(**data)


# ============================================================
# Position
# ============================================================


def test_position_can_be_created() -> None:
    position = build_position()

    assert position.symbol == "AAPL"
    assert position.market is Market.US
    assert position.quantity == Decimal("100")
    assert position.average_cost == Decimal("200.50")


def test_position_normalizes_symbol() -> None:
    position = build_position(
        symbol="  aapl  ",
    )

    assert position.symbol == "AAPL"


def test_position_has_unique_id() -> None:
    first = build_position()
    second = build_position()

    assert (
        first.position_id
        != second.position_id
    )


def test_position_cost_basis() -> None:
    position = build_position(
        quantity=Decimal("100"),
        average_cost=Decimal("200.50"),
    )

    assert (
        position.cost_basis
        == Decimal("20050.00")
    )


def test_position_instrument_key() -> None:
    position = build_position()

    assert (
        position.instrument_key
        == "US:AAPL"
    )


def test_position_rejects_empty_symbol() -> None:
    with pytest.raises(
        ValidationError,
    ):
        build_position(
            symbol="   ",
        )


def test_position_rejects_zero_quantity() -> None:
    with pytest.raises(
        ValidationError,
    ):
        build_position(
            quantity=Decimal("0"),
        )


def test_position_rejects_negative_quantity() -> None:
    with pytest.raises(
        ValidationError,
    ):
        build_position(
            quantity=Decimal("-1"),
        )


def test_position_rejects_zero_average_cost() -> None:
    with pytest.raises(
        ValidationError,
    ):
        build_position(
            average_cost=Decimal("0"),
        )


def test_position_rejects_negative_average_cost() -> None:
    with pytest.raises(
        ValidationError,
    ):
        build_position(
            average_cost=Decimal("-1"),
        )


def test_position_rejects_extra_fields() -> None:
    with pytest.raises(
        ValidationError,
    ):
        build_position(
            invalid_field="x",
        )


def test_position_is_immutable() -> None:
    position = build_position()

    with pytest.raises(
        ValidationError,
    ):
        position.quantity = Decimal("200")  # type: ignore[misc]


def test_position_normalizes_timestamp_to_utc() -> None:
    japan_timezone = timezone(
        timedelta(hours=9)
    )

    timestamp = datetime(
        2026,
        9,
        4,
        21,
        0,
        0,
        tzinfo=japan_timezone,
    )

    position = build_position(
        created_at=timestamp,
    )

    assert (
        position.created_at
        == datetime(
            2026,
            9,
            4,
            12,
            0,
            0,
            tzinfo=UTC,
        )
    )

    assert (
        position.created_at.tzinfo
        is UTC
    )