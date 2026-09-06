from __future__ import annotations

from datetime import (
    UTC,
    datetime,
)
from unittest.mock import Mock

import pytest

from libs.observability import (
    CloudWatchMetricSink,
    MetricPoint,
    MetricUnit,
)

pytestmark = pytest.mark.unit


def build_metric() -> MetricPoint:
    return MetricPoint(
        name="RiskAlertsGenerated",
        value=1.0,
        unit=MetricUnit.COUNT,
        dimensions={
            "Service": "risk-engine",
            "Environment": "local",
            "Severity": "CRITICAL",
        },
        timestamp=datetime(
            2026,
            9,
            6,
            4,
            30,
            tzinfo=UTC,
        ),
    )


def test_cloudwatch_sink_emits_metric() -> None:
    client = Mock()

    sink = CloudWatchMetricSink(
        client=client
    )

    metric = build_metric()

    sink.emit(
        metric
    )

    client.put_metric_data.assert_called_once()

    kwargs = (
        client.put_metric_data
        .call_args.kwargs
    )

    assert (
        kwargs["Namespace"]
        == "RealStock/Applications"
    )

    assert len(
        kwargs["MetricData"]
    ) == 1

    metric_data = (
        kwargs["MetricData"][0]
    )

    assert (
        metric_data["MetricName"]
        == "RiskAlertsGenerated"
    )

    assert (
        metric_data["Value"]
        == 1.0
    )

    assert (
        metric_data["Unit"]
        == "Count"
    )

    assert (
        metric_data["Timestamp"]
        == metric.timestamp
    )


def test_cloudwatch_sink_maps_dimensions() -> None:
    client = Mock()

    sink = CloudWatchMetricSink(
        client=client
    )

    sink.emit(
        build_metric()
    )

    metric_data = (
        client.put_metric_data
        .call_args.kwargs[
            "MetricData"
        ][0]
    )

    dimensions = {
        dimension["Name"]:
            dimension["Value"]
        for dimension
        in metric_data["Dimensions"]
    }

    assert dimensions == {
        "Service": "risk-engine",
        "Environment": "local",
        "Severity": "CRITICAL",
    }


def test_cloudwatch_sink_supports_custom_namespace() -> None:
    client = Mock()

    sink = CloudWatchMetricSink(
        client=client,
        namespace="RealStock/Test",
    )

    sink.emit(
        build_metric()
    )

    assert (
        client.put_metric_data
        .call_args.kwargs[
            "Namespace"
        ]
        == "RealStock/Test"
    )


def test_cloudwatch_sink_rejects_empty_namespace() -> None:
    with pytest.raises(
        ValueError,
        match="namespace",
    ):
        CloudWatchMetricSink(
            client=Mock(),
            namespace=" ",
        )


def test_cloudwatch_sink_propagates_backend_failure() -> None:
    client = Mock()

    client.put_metric_data.side_effect = (
        RuntimeError(
            "cloudwatch unavailable"
        )
    )

    sink = CloudWatchMetricSink(
        client=client
    )

    with pytest.raises(
        RuntimeError,
        match="cloudwatch unavailable",
    ):
        sink.emit(
            build_metric()
        )