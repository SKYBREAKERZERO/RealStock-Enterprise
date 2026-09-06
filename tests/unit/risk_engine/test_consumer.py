from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock

import pytest

from libs.domain.market import (
    Market,
    MarketQuote,
)
from libs.events import (
    create_market_quote_event,
)
from services.risk_engine import (
    EventBridgePublishResult,
    EventBridgeRiskEventPublisher,
    InMemoryQuoteStateStore,
    InvalidKinesisMarketEventError,
    KinesisRiskEngineConsumer,
    RiskEngineService,
)

pytestmark = pytest.mark.unit


BASE_TIME = datetime(
    2026,
    9,
    6,
    9,
    0,
    tzinfo=UTC,
)


def build_quote_event(
    *,
    price: Decimal,
    seconds: int,
):
    quote = MarketQuote(
        symbol="AAPL",
        market=Market.US,
        bid_price=price,
        ask_price=price,
        bid_size=100,
        ask_size=100,
        timestamp=(
            BASE_TIME
            + timedelta(seconds=seconds)
        ),
    )

    return create_market_quote_event(
        quote
    )


def build_record(
    event,
) -> dict[str, object]:
    return {
        "Data": (
            event.to_event_json()
            .encode("utf-8")
        ),
        "PartitionKey": "AAPL",
        "SequenceNumber": "1",
    }


def test_first_quote_initializes_state_without_publish() -> None:
    publisher = Mock(
        spec=EventBridgeRiskEventPublisher
    )

    consumer = KinesisRiskEngineConsumer(
        risk_engine=RiskEngineService(
            state_store=(
                InMemoryQuoteStateStore()
            )
        ),
        publisher=publisher,
    )

    event = build_quote_event(
        price=Decimal("100"),
        seconds=1,
    )

    result = consumer.process_record(
        build_record(event)
    )

    assert (
        result.market_event_id
        == str(event.event_id)
    )

    assert result.alert_generated is False
    assert result.risk_event_id is None

    publisher.publish.assert_not_called()


def test_price_move_generates_and_publishes_risk_event() -> None:
    publisher = Mock(
        spec=EventBridgeRiskEventPublisher
    )

    publisher.publish.return_value = (
        EventBridgePublishResult(
            event_id="eventbridge-001"
        )
    )

    consumer = KinesisRiskEngineConsumer(
        risk_engine=RiskEngineService(
            state_store=(
                InMemoryQuoteStateStore()
            )
        ),
        publisher=publisher,
    )

    first_event = build_quote_event(
        price=Decimal("100"),
        seconds=1,
    )

    second_event = build_quote_event(
        price=Decimal("94"),
        seconds=2,
    )

    consumer.process_record(
        build_record(first_event)
    )

    result = consumer.process_record(
        build_record(second_event)
    )

    assert result.alert_generated is True
    assert result.risk_event_id is not None

    assert (
        result.eventbridge_event_id
        == "eventbridge-001"
    )

    publisher.publish.assert_called_once()

    risk_event = (
        publisher.publish.call_args.args[0]
    )

    assert (
        risk_event.event_type
        == "risk.alert.detected"
    )

    assert (
        risk_event.correlation_id
        == second_event.correlation_id
    )

    assert (
        risk_event.causation_id
        == second_event.event_id
    )

    assert (
        risk_event.payload["symbol"]
        == "AAPL"
    )

    assert (
        Decimal(
            risk_event.payload[
                "observed_value"
            ]
        )
        == Decimal("-6")
    )


def test_missing_data_is_rejected() -> None:
    consumer = KinesisRiskEngineConsumer(
        risk_engine=Mock(),
        publisher=Mock(),
    )

    with pytest.raises(
        InvalidKinesisMarketEventError,
        match="Data",
    ):
        consumer.process_record(
            {}
        )


def test_invalid_json_is_rejected() -> None:
    consumer = KinesisRiskEngineConsumer(
        risk_engine=Mock(),
        publisher=Mock(),
    )

    with pytest.raises(
        InvalidKinesisMarketEventError,
        match="EventEnvelope",
    ):
        consumer.process_record(
            {
                "Data": b"{invalid-json",
            }
        )


def test_invalid_data_type_is_rejected() -> None:
    consumer = KinesisRiskEngineConsumer(
        risk_engine=Mock(),
        publisher=Mock(),
    )

    with pytest.raises(
        InvalidKinesisMarketEventError,
        match="bytes or string",
    ):
        consumer.process_record(
            {
                "Data": 123,
            }
        )


def test_eventbridge_failure_propagates() -> None:
    publisher = Mock(
        spec=EventBridgeRiskEventPublisher
    )

    publisher.publish.side_effect = (
        RuntimeError(
            "EventBridge unavailable"
        )
    )

    consumer = KinesisRiskEngineConsumer(
        risk_engine=RiskEngineService(
            state_store=(
                InMemoryQuoteStateStore()
            )
        ),
        publisher=publisher,
    )

    consumer.process_record(
        build_record(
            build_quote_event(
                price=Decimal("100"),
                seconds=1,
            )
        )
    )

    with pytest.raises(
        RuntimeError,
        match="EventBridge unavailable",
    ):
        consumer.process_record(
            build_record(
                build_quote_event(
                    price=Decimal("94"),
                    seconds=2,
                )
            )
        )