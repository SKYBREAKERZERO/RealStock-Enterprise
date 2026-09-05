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
    MarketTrade,
    TradeSide,
)
from libs.domain.risk import (
    RiskSeverity,
)
from libs.events import (
    create_market_quote_event,
    create_market_trade_event,
)
from services.risk_engine import (
    InMemoryQuoteStateStore,
    RiskEngineService,
)

pytestmark = pytest.mark.unit


BASE_TIMESTAMP = datetime(
    2026,
    9,
    5,
    7,
    0,
    0,
    tzinfo=UTC,
)


def build_quote(
    *,
    price: Decimal,
    seconds: int,
    symbol: str = "AAPL",
    market: Market = Market.US,
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
            + timedelta(
                seconds=seconds
            )
        ),
    )


def process_quote(
    service: RiskEngineService,
    *,
    price: Decimal,
    seconds: int,
    symbol: str = "AAPL",
    market: Market = Market.US,
):
    quote = build_quote(
        price=price,
        seconds=seconds,
        symbol=symbol,
        market=market,
    )

    event = create_market_quote_event(
        quote
    )

    return (
        service.process_event(
            event
        ),
        event,
    )


def test_first_quote_initializes_state_without_alert() -> None:
    state = InMemoryQuoteStateStore()

    service = RiskEngineService(
        state_store=state,
    )

    result, _ = process_quote(
        service,
        price=Decimal("100"),
        seconds=1,
    )

    assert result is None

    stored = state.get_quote(
        market=Market.US,
        symbol="AAPL",
    )

    assert stored is not None

    assert (
        stored.mid_price
        == Decimal("100")
    )


def test_below_threshold_updates_state_without_alert() -> None:
    state = InMemoryQuoteStateStore()

    service = RiskEngineService(
        state_store=state,
    )

    process_quote(
        service,
        price=Decimal("100"),
        seconds=1,
    )

    result, _ = process_quote(
        service,
        price=Decimal("101"),
        seconds=2,
    )

    assert result is None

    stored = state.get_quote(
        market=Market.US,
        symbol="AAPL",
    )

    assert stored is not None

    assert (
        stored.mid_price
        == Decimal("101")
    )


def test_warning_risk_event_is_created() -> None:
    service = RiskEngineService()

    process_quote(
        service,
        price=Decimal("100"),
        seconds=1,
    )

    risk_event, source_event = (
        process_quote(
            service,
            price=Decimal("102"),
            seconds=2,
        )
    )

    assert risk_event is not None

    assert (
        risk_event.event_type
        == "risk.alert.detected"
    )

    assert (
        risk_event.payload["severity"]
        == RiskSeverity.WARNING.value
    )

    assert (
        Decimal(
            risk_event.payload[
                "observed_value"
            ]
        )
        == Decimal("2")
    )

    assert (
        risk_event.correlation_id
        == source_event.correlation_id
    )

    assert (
        risk_event.causation_id
        == source_event.event_id
    )


def test_critical_negative_move_is_created() -> None:
    service = RiskEngineService()

    process_quote(
        service,
        price=Decimal("100"),
        seconds=1,
    )

    risk_event, _ = process_quote(
        service,
        price=Decimal("94"),
        seconds=2,
    )

    assert risk_event is not None

    assert (
        risk_event.payload["severity"]
        == RiskSeverity.CRITICAL.value
    )

    assert (
        Decimal(
            risk_event.payload[
                "observed_value"
            ]
        )
        == Decimal("-6")
    )


def test_non_quote_event_is_ignored() -> None:
    service = RiskEngineService()

    trade = MarketTrade(
        trade_id="trade-001",
        symbol="AAPL",
        market=Market.US,
        price=Decimal("100"),
        quantity=10,
        side=TradeSide.BUY,
        timestamp=BASE_TIMESTAMP,
    )

    event = create_market_trade_event(
        trade
    )

    result = service.process_event(
        event
    )

    assert result is None


def test_out_of_order_quote_is_ignored() -> None:
    state = InMemoryQuoteStateStore()

    service = RiskEngineService(
        state_store=state,
    )

    process_quote(
        service,
        price=Decimal("100"),
        seconds=10,
    )

    result, _ = process_quote(
        service,
        price=Decimal("200"),
        seconds=5,
    )

    assert result is None

    stored = state.get_quote(
        market=Market.US,
        symbol="AAPL",
    )

    assert stored is not None

    assert (
        stored.mid_price
        == Decimal("100")
    )

    assert (
        stored.timestamp
        == BASE_TIMESTAMP
        + timedelta(seconds=10)
    )


def test_instruments_have_independent_state() -> None:
    service = RiskEngineService()

    process_quote(
        service,
        price=Decimal("100"),
        seconds=1,
        symbol="AAPL",
    )

    process_quote(
        service,
        price=Decimal("200"),
        seconds=1,
        symbol="MSFT",
    )

    aapl_event, _ = process_quote(
        service,
        price=Decimal("106"),
        seconds=2,
        symbol="AAPL",
    )

    msft_event, _ = process_quote(
        service,
        price=Decimal("201"),
        seconds=2,
        symbol="MSFT",
    )

    assert aapl_event is not None

    assert (
        aapl_event.payload["symbol"]
        == "AAPL"
    )

    assert msft_event is None