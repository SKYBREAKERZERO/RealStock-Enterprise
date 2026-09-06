from __future__ import annotations

import time

import pytest

from libs.observability import (
    InMemoryMetricSink,
    MetricsRecorder,
    MetricUnit,
    NoopMetricSink,
)

pytestmark = pytest.mark.unit


def test_increment_emits_count_metric() -> None:
    sink = InMemoryMetricSink()

    recorder = MetricsRecorder(
        sink=sink
    )

    recorder.increment(
        "MarketEventsProcessed"
    )

    assert len(sink.metrics) == 1

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
            "Service": "risk-engine",
            "Environment": "local",
        }
    )


def test_call_dimensions_override_defaults() -> None:
    sink = InMemoryMetricSink()

    recorder = MetricsRecorder(
        sink=sink,
        default_dimensions={
            "Service": "risk-engine",
            "Environment": "local",
        },
    )

    recorder.increment(
        "RiskAlertsGenerated",
        dimensions={
            "Environment": "test",
            "Severity": "CRITICAL",
        },
    )

    assert (
        sink.metrics[0].dimensions
        == {
            "Service": "risk-engine",
            "Environment": "test",
            "Severity": "CRITICAL",
        }
    )


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

    assert len(sink.metrics) == 1

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

    assert len(sink.metrics) == 1

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
                " ": "risk-engine"
            },
        )

    with pytest.raises(
        ValueError,
        match="dimension value",
    ):
        MetricsRecorder(
            sink=InMemoryMetricSink(),
            default_dimensions={
                "Service": " "
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

    assert len(sink.metrics) == 2

    sink.clear()

    assert sink.metrics == ()


def test_noop_sink_accepts_metrics() -> None:
    recorder = MetricsRecorder(
        sink=NoopMetricSink()
    )

    recorder.increment(
        "MarketEventsProcessed"
    )