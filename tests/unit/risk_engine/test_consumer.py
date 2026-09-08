from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)
from opentelemetry.trace import SpanKind

from libs.domain.market import (
    Market,
    MarketQuote,
)
from libs.events import (
    create_market_quote_event,
)
from libs.observability import (
    InMemoryMetricSink,
    MetricsRecorder,
    MetricUnit,
    create_tracing_runtime,
    inject_trace_context,
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


# =========================================================
# Functional behavior
# =========================================================


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


# =========================================================
# Structured logging
# =========================================================


def test_processing_logs_market_event_context(
    caplog,
) -> None:
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

    with caplog.at_level(
        logging.INFO,
        logger=(
            "realstock."
            "risk_engine.consumer"
        ),
    ):
        consumer.process_record(
            build_record(event)
        )

    received_record = next(
        record
        for record in caplog.records
        if (
            record.getMessage()
            == "market event received"
        )
    )

    fields = received_record.structured_fields

    assert (
        fields["event_type"]
        == event.event_type
    )


def test_risk_alert_log_contains_business_fields(
    caplog,
) -> None:
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

    consumer.process_record(
        build_record(
            build_quote_event(
                price=Decimal("100"),
                seconds=1,
            )
        )
    )

    with caplog.at_level(
        logging.WARNING,
        logger=(
            "realstock."
            "risk_engine.consumer"
        ),
    ):
        consumer.process_record(
            build_record(
                build_quote_event(
                    price=Decimal("94"),
                    seconds=2,
                )
            )
        )

    risk_record = next(
        record
        for record in caplog.records
        if (
            record.getMessage()
            == "risk alert generated"
        )
    )

    fields = risk_record.structured_fields

    assert (
        fields["severity"]
        == "CRITICAL"
    )

    assert (
        fields["risk_type"]
        == "PRICE_MOVE_PERCENT"
    )

    assert (
        fields["market"]
        == "US"
    )

    assert (
        fields["symbol"]
        == "AAPL"
    )

    assert (
        Decimal(
            fields[
                "observed_value"
            ]
        )
        == Decimal("-6")
    )

    assert (
        Decimal(
            fields["threshold"]
        )
        == Decimal("5")
    )


def test_eventbridge_failure_is_logged(
    caplog,
) -> None:
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

    with caplog.at_level(
        logging.ERROR,
        logger=(
            "realstock."
            "risk_engine.consumer"
        ),
    ):
        with pytest.raises(
            RuntimeError,
            match=(
                "EventBridge unavailable"
            ),
        ):
            consumer.process_record(
                build_record(
                    build_quote_event(
                        price=Decimal("94"),
                        seconds=2,
                    )
                )
            )

    error_record = next(
        record
        for record in caplog.records
        if (
            record.getMessage()
            == "risk event processing failed"
        )
    )

    assert (
        error_record.levelno
        == logging.ERROR
    )

    assert (
        error_record.exc_info
        is not None
    )

    fields = error_record.structured_fields

    assert (
        fields["event_type"]
        == "market.quote.received"
    )


# =========================================================
# Metrics
# =========================================================


def test_metrics_record_event_without_alert() -> None:
    publisher = Mock(
        spec=EventBridgeRiskEventPublisher
    )

    sink = InMemoryMetricSink()

    metrics = MetricsRecorder(
        sink=sink
    )

    consumer = KinesisRiskEngineConsumer(
        risk_engine=RiskEngineService(
            state_store=(
                InMemoryQuoteStateStore()
            )
        ),
        publisher=publisher,
        metrics=metrics,
    )

    event = build_quote_event(
        price=Decimal("100"),
        seconds=1,
    )

    consumer.process_record(
        build_record(event)
    )

    names = [
        metric.name
        for metric in sink.metrics
    ]

    assert (
        "MarketEventsProcessed"
        in names
    )

    assert (
        "RiskProcessingLatency"
        in names
    )

    assert (
        "RiskAlertsGenerated"
        not in names
    )

    assert (
        "RiskEventsPublished"
        not in names
    )

    assert (
        "RiskProcessingFailures"
        not in names
    )

    processed = next(
        metric
        for metric in sink.metrics
        if (
            metric.name
            == "MarketEventsProcessed"
        )
    )

    assert (
        processed.unit
        == MetricUnit.COUNT
    )

    assert (
        processed.dimensions[
            "EventType"
        ]
        == event.event_type
    )


def test_metrics_record_generated_and_published_alert() -> None:
    publisher = Mock(
        spec=EventBridgeRiskEventPublisher
    )

    publisher.publish.return_value = (
        EventBridgePublishResult(
            event_id="eventbridge-001"
        )
    )

    sink = InMemoryMetricSink()

    consumer = KinesisRiskEngineConsumer(
        risk_engine=RiskEngineService(
            state_store=(
                InMemoryQuoteStateStore()
            )
        ),
        publisher=publisher,
        metrics=MetricsRecorder(
            sink=sink
        ),
    )

    consumer.process_record(
        build_record(
            build_quote_event(
                price=Decimal("100"),
                seconds=1,
            )
        )
    )

    sink.clear()

    consumer.process_record(
        build_record(
            build_quote_event(
                price=Decimal("94"),
                seconds=2,
            )
        )
    )

    generated = next(
        metric
        for metric in sink.metrics
        if (
            metric.name
            == "RiskAlertsGenerated"
        )
    )

    published = next(
        metric
        for metric in sink.metrics
        if (
            metric.name
            == "RiskEventsPublished"
        )
    )

    assert (
        generated.value
        == 1.0
    )

    assert (
        generated.dimensions
        == {
            "Severity": "CRITICAL",
            "Market": "US",
        }
    )

    assert (
        published.value
        == 1.0
    )

    assert (
        published.dimensions
        == {
            "Severity": "CRITICAL",
            "Market": "US",
        }
    )


def test_metrics_record_processing_failure() -> None:
    publisher = Mock(
        spec=EventBridgeRiskEventPublisher
    )

    publisher.publish.side_effect = (
        RuntimeError(
            "EventBridge unavailable"
        )
    )

    sink = InMemoryMetricSink()

    consumer = KinesisRiskEngineConsumer(
        risk_engine=RiskEngineService(
            state_store=(
                InMemoryQuoteStateStore()
            )
        ),
        publisher=publisher,
        metrics=MetricsRecorder(
            sink=sink
        ),
    )

    consumer.process_record(
        build_record(
            build_quote_event(
                price=Decimal("100"),
                seconds=1,
            )
        )
    )

    sink.clear()

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

    names = [
        metric.name
        for metric in sink.metrics
    ]

    assert (
        "RiskAlertsGenerated"
        in names
    )

    assert (
        "RiskEventsPublished"
        not in names
    )

    assert (
        "RiskProcessingFailures"
        in names
    )

    assert (
        "RiskProcessingLatency"
        in names
    )


def test_invalid_record_records_failure_and_latency() -> None:
    sink = InMemoryMetricSink()

    consumer = KinesisRiskEngineConsumer(
        risk_engine=Mock(),
        publisher=Mock(),
        metrics=MetricsRecorder(
            sink=sink
        ),
    )

    with pytest.raises(
        InvalidKinesisMarketEventError,
    ):
        consumer.process_record(
            {
                "Data": b"{broken-json",
            }
        )

    names = [
        metric.name
        for metric in sink.metrics
    ]

    assert (
        "RiskProcessingFailures"
        in names
    )

    assert (
        "RiskProcessingLatency"
        in names
    )

    assert (
        "MarketEventsProcessed"
        not in names
    )


# =========================================================
# Distributed tracing
# =========================================================


def test_risk_processing_creates_consumer_span() -> None:
    exporter = InMemorySpanExporter()

    runtime = create_tracing_runtime(
        service_name="risk-engine",
        environment="test",
        exporter=exporter,
    )

    publisher = Mock(
        spec=EventBridgeRiskEventPublisher
    )

    event = build_quote_event(
        price=Decimal("100"),
        seconds=1,
    )

    consumer = KinesisRiskEngineConsumer(
        risk_engine=RiskEngineService(
            state_store=(
                InMemoryQuoteStateStore()
            )
        ),
        publisher=publisher,
        tracer=runtime.tracer,
    )

    try:
        result = consumer.process_record(
            build_record(
                event
            )
        )

        assert (
            result.market_event_id
            == str(
                event.event_id
            )
        )

        assert runtime.force_flush()

        spans = (
            exporter.get_finished_spans()
        )

        risk_span = next(
            span
            for span in spans
            if span.name
            == "risk.process"
        )

        assert (
            risk_span.kind
            == SpanKind.CONSUMER
        )

        assert (
            risk_span.attributes[
                "messaging.system"
            ]
            == "aws_kinesis"
        )

        assert (
            risk_span.attributes[
                "messaging.operation"
            ]
            == "process"
        )

        assert (
            risk_span.attributes[
                "realstock.event_type"
            ]
            == event.event_type
        )

        assert (
            risk_span.attributes[
                "realstock.event_id"
            ]
            == str(
                event.event_id
            )
        )

        assert (
            risk_span.attributes[
                "realstock.correlation_id"
            ]
            == str(
                event.correlation_id
            )
        )

    finally:
        runtime.shutdown()


def test_eventbridge_publish_runs_inside_risk_span() -> None:
    exporter = InMemorySpanExporter()

    runtime = create_tracing_runtime(
        service_name="risk-engine",
        environment="test",
        exporter=exporter,
    )

    publisher = Mock(
        spec=EventBridgeRiskEventPublisher
    )

    captured_carrier: dict[
        str,
        str,
    ] = {}

    def publish_side_effect(
        event,
    ):
        captured_carrier.update(
            inject_trace_context()
        )

        return EventBridgePublishResult(
            event_id="eventbridge-001"
        )

    publisher.publish.side_effect = (
        publish_side_effect
    )

    consumer = KinesisRiskEngineConsumer(
        risk_engine=RiskEngineService(
            state_store=(
                InMemoryQuoteStateStore()
            )
        ),
        publisher=publisher,
        tracer=runtime.tracer,
    )

    first_event = build_quote_event(
        price=Decimal("100"),
        seconds=1,
    )

    second_event = build_quote_event(
        price=Decimal("94"),
        seconds=2,
    )

    try:
        consumer.process_record(
            build_record(
                first_event
            )
        )

        result = consumer.process_record(
            build_record(
                second_event
            )
        )

        assert (
            result.alert_generated
            is True
        )

        assert (
            "traceparent"
            in captured_carrier
        )

        assert runtime.force_flush()

        spans = (
            exporter.get_finished_spans()
        )

        second_span = next(
            span
            for span in spans
            if (
                span.name
                == "risk.process"
                and span.attributes[
                    "realstock.event_id"
                ]
                == str(
                    second_event.event_id
                )
            )
        )

        traceparent = (
            captured_carrier[
                "traceparent"
            ]
        )

        parts = traceparent.split(
            "-"
        )

        assert len(parts) == 4

        assert (
            parts[1]
            == (
                f"{second_span.context.trace_id:032x}"
            )
        )

        assert (
            parts[2]
            == (
                f"{second_span.context.span_id:016x}"
            )
        )

    finally:
        runtime.shutdown()


def test_risk_processing_continues_incoming_remote_trace() -> None:
    upstream_exporter = (
        InMemorySpanExporter()
    )

    risk_exporter = (
        InMemorySpanExporter()
    )

    upstream_runtime = (
        create_tracing_runtime(
            service_name="market-ingestor",
            environment="test",
            exporter=upstream_exporter,
        )
    )

    risk_runtime = (
        create_tracing_runtime(
            service_name="risk-engine",
            environment="test",
            exporter=risk_exporter,
        )
    )

    publisher = Mock(
        spec=EventBridgeRiskEventPublisher
    )

    event = build_quote_event(
        price=Decimal("100"),
        seconds=1,
    )

    try:
        with (
            upstream_runtime
            .tracer
            .start_as_current_span(
                "kinesis.publish"
            )
        ) as upstream_span:
            upstream_context = (
                upstream_span
                .get_span_context()
            )

            carrier = (
                inject_trace_context()
            )

        assert (
            "traceparent"
            in carrier
        )

        traced_event = (
            event.model_copy(
                update={
                    "trace_context":
                        carrier
                }
            )
        )

        consumer = (
            KinesisRiskEngineConsumer(
                risk_engine=(
                    RiskEngineService(
                        state_store=(
                            InMemoryQuoteStateStore()
                        )
                    )
                ),
                publisher=publisher,
                tracer=(
                    risk_runtime.tracer
                ),
            )
        )

        result = consumer.process_record(
            build_record(
                traced_event
            )
        )

        assert (
            result.market_event_id
            == str(
                event.event_id
            )
        )

        assert risk_runtime.force_flush()

        spans = (
            risk_exporter
            .get_finished_spans()
        )

        risk_span = next(
            span
            for span in spans
            if span.name
            == "risk.process"
        )

        assert (
            risk_span.context.trace_id
            == upstream_context.trace_id
        )

        assert (
            risk_span.context.span_id
            != upstream_context.span_id
        )

        assert (
            risk_span.parent
            is not None
        )

        assert (
            risk_span.parent.span_id
            == upstream_context.span_id
        )

        assert (
            risk_span.parent.trace_id
            == upstream_context.trace_id
        )

        assert (
            risk_span.parent.is_remote
        )

    finally:
        upstream_runtime.shutdown()
        risk_runtime.shutdown()