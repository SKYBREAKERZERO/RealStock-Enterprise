from __future__ import annotations

import logging
import time

import pytest

from libs.observability import (
    InMemoryMetricSink,
    MetricsRecorder,
    MetricUnit,
    NoopMetricSink,
    ResilientMetricSink,
)

pytestmark = pytest.mark.unit


class FailingMetricSink:
    def emit(
        self,
        metric,
    ) -> None:
        del metric

        raise RuntimeError(
            "backend unavailable"
        )


def test_increment_emits_count_metric() -> None:
    sink = InMemoryMetricSink()

    recorder = MetricsRecorder(
        sink=sink
    )

    recorder.increment(
        "MarketEventsProcessed"
    )

    assert len(
        sink.metrics
    ) == 1

    metric = sink.metrics[0]

    assert (
        metric.name
        == "MarketEventsProcessed"
    )

    assert metric.value == 1.0

    assert (
        metric.unit
        == MetricUnit.COUNT
    )

    assert metric.dimensions == {}

    assert (
        metric.timestamp.tzinfo
        is not None
    )

    assert (
        metric.timestamp
        .utcoffset()
        .total_seconds()
        == 0
    )


def test_increment_supports_custom_value() -> None:
    sink = InMemoryMetricSink()

    recorder = MetricsRecorder(
        sink=sink
    )

    recorder.increment(
        "MessagesProcessed",
        value=5,
    )

    metric = sink.metrics[0]

    assert metric.value == 5.0


def test_default_dimensions_are_applied() -> None:
    sink = InMemoryMetricSink()

    recorder = MetricsRecorder(
        sink=sink,
        default_dimensions={
            "Service": "risk-engine",
            "Environment": "local",
        },
    )

    recorder.increment(
        "MarketEventsProcessed"
    )

    assert (
        sink.metrics[0].dimensions
        == {
            "Service":
                "risk-engine",
            "Environment":
                "local",
        }
    )


def test_call_dimensions_override_defaults() -> None:
    sink = InMemoryMetricSink()

    recorder = MetricsRecorder(
        sink=sink,
        default_dimensions={
            "Service":
                "risk-engine",
            "Environment":
                "local",
        },
    )

    recorder.increment(
        "RiskAlertsGenerated",
        dimensions={
            "Environment":
                "test",
            "Severity":
                "CRITICAL",
        },
    )

    assert (
        sink.metrics[0].dimensions
        == {
            "Service":
                "risk-engine",
            "Environment":
                "test",
            "Severity":
                "CRITICAL",
        }
    )


def test_call_dimensions_do_not_mutate_defaults() -> None:
    sink = InMemoryMetricSink()

    recorder = MetricsRecorder(
        sink=sink,
        default_dimensions={
            "Service":
                "risk-engine",
            "Environment":
                "local",
        },
    )

    recorder.increment(
        "RiskAlertsGenerated",
        dimensions={
            "Environment":
                "test",
        },
    )

    recorder.increment(
        "MarketEventsProcessed"
    )

    assert (
        sink.metrics[1].dimensions
        == {
            "Service":
                "risk-engine",
            "Environment":
                "local",
        }
    )


def test_increment_does_not_mutate_call_dimensions() -> None:
    sink = InMemoryMetricSink()

    recorder = MetricsRecorder(
        sink=sink,
        default_dimensions={
            "Service":
                "risk-engine",
        },
    )

    dimensions = {
        "Severity":
            "CRITICAL",
    }

    recorder.increment(
        "RiskAlertsGenerated",
        dimensions=dimensions,
    )

    assert dimensions == {
        "Severity":
            "CRITICAL",
    }


def test_timer_records_elapsed_milliseconds() -> None:
    sink = InMemoryMetricSink()

    recorder = MetricsRecorder(
        sink=sink
    )

    with recorder.timer(
        "RiskProcessingLatency"
    ):
        time.sleep(
            0.001
        )

    assert len(
        sink.metrics
    ) == 1

    metric = sink.metrics[0]

    assert (
        metric.name
        == "RiskProcessingLatency"
    )

    assert (
        metric.unit
        == MetricUnit.MILLISECONDS
    )

    assert metric.value > 0


def test_timer_applies_dimensions() -> None:
    sink = InMemoryMetricSink()

    recorder = MetricsRecorder(
        sink=sink,
        default_dimensions={
            "Service":
                "risk-engine",
        },
    )

    with recorder.timer(
        "RiskProcessingLatency",
        dimensions={
            "Market":
                "US",
        },
    ):
        pass

    assert (
        sink.metrics[0].dimensions
        == {
            "Service":
                "risk-engine",
            "Market":
                "US",
        }
    )


def test_timer_records_metric_when_scope_fails() -> None:
    sink = InMemoryMetricSink()

    recorder = MetricsRecorder(
        sink=sink
    )

    with pytest.raises(
        RuntimeError,
        match="boom",
    ):
        with recorder.timer(
            "RiskProcessingLatency"
        ):
            raise RuntimeError(
                "boom"
            )

    assert len(
        sink.metrics
    ) == 1

    assert (
        sink.metrics[0].name
        == "RiskProcessingLatency"
    )

    assert (
        sink.metrics[0].unit
        == MetricUnit.MILLISECONDS
    )


def test_invalid_metric_name_is_rejected() -> None:
    recorder = MetricsRecorder(
        sink=InMemoryMetricSink()
    )

    with pytest.raises(
        ValueError,
        match="metric name",
    ):
        recorder.increment(
            " "
        )


def test_invalid_dimensions_are_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="dimension name",
    ):
        MetricsRecorder(
            sink=InMemoryMetricSink(),
            default_dimensions={
                " ":
                    "risk-engine"
            },
        )

    with pytest.raises(
        ValueError,
        match="dimension value",
    ):
        MetricsRecorder(
            sink=InMemoryMetricSink(),
            default_dimensions={
                "Service":
                    " "
            },
        )


def test_in_memory_sink_can_be_cleared() -> None:
    sink = InMemoryMetricSink()

    recorder = MetricsRecorder(
        sink=sink
    )

    recorder.increment(
        "MetricA"
    )

    recorder.increment(
        "MetricB"
    )

    assert len(
        sink.metrics
    ) == 2

    sink.clear()

    assert sink.metrics == ()


def test_in_memory_sink_exposes_immutable_snapshot() -> None:
    sink = InMemoryMetricSink()

    recorder = MetricsRecorder(
        sink=sink
    )

    recorder.increment(
        "MetricA"
    )

    metrics = sink.metrics

    assert isinstance(
        metrics,
        tuple,
    )

    assert len(
        metrics
    ) == 1


def test_noop_sink_accepts_metrics() -> None:
    recorder = MetricsRecorder(
        sink=NoopMetricSink()
    )

    recorder.increment(
        "MarketEventsProcessed"
    )


def test_resilient_sink_delegates_successful_metric() -> None:
    inner_sink = (
        InMemoryMetricSink()
    )

    sink = ResilientMetricSink(
        sink=inner_sink
    )

    recorder = MetricsRecorder(
        sink=sink
    )

    recorder.increment(
        "MarketEventsProcessed"
    )

    assert len(
        inner_sink.metrics
    ) == 1

    assert (
        inner_sink.metrics[0].name
        == "MarketEventsProcessed"
    )


def test_resilient_sink_suppresses_backend_failure() -> None:
    recorder = MetricsRecorder(
        sink=ResilientMetricSink(
            sink=FailingMetricSink()
        )
    )

    recorder.increment(
        "MarketEventsProcessed"
    )


def test_resilient_sink_logs_backend_failure(
    caplog,
) -> None:
    recorder = MetricsRecorder(
        sink=ResilientMetricSink(
            sink=FailingMetricSink()
        )
    )

    with caplog.at_level(
        logging.ERROR
    ):
        recorder.increment(
            "RiskAlertsGenerated"
        )

    records = [
        record
        for record in caplog.records
        if (
            record.getMessage()
            == "metric emission failed"
        )
    ]

    assert len(
        records
    ) == 1

    fields = records[0].structured_fields

    assert (
        fields["metric_name"]
        == "RiskAlertsGenerated"
    )

    assert (
        fields["metric_unit"]
        == "Count"
    )


def test_resilient_sink_preserves_business_exception() -> None:
    recorder = MetricsRecorder(
        sink=ResilientMetricSink(
            sink=FailingMetricSink()
        )
    )

    with pytest.raises(
        ValueError,
        match="business failed",
    ):
        with recorder.timer(
            "RiskProcessingLatency"
        ):
            raise ValueError(
                "business failed"
            )