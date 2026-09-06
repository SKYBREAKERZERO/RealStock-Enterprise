from __future__ import annotations

import time
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from libs.aws import get_cloudwatch_client
from libs.observability import (
    CloudWatchMetricSink,
    MetricPoint,
    MetricUnit,
)

pytestmark = pytest.mark.integration


def wait_for_metric(
    *,
    client,
    namespace: str,
    metric_name: str,
    timeout_seconds: float = 5.0,
) -> dict:
    deadline = (
        time.monotonic()
        + timeout_seconds
    )

    while time.monotonic() < deadline:
        response = client.list_metrics(
            Namespace=namespace,
            MetricName=metric_name,
        )

        metrics = response.get(
            "Metrics",
            [],
        )

        if metrics:
            return metrics[0]

        time.sleep(0.25)

    raise AssertionError(
        "CloudWatch metric was not visible "
        f"within {timeout_seconds} seconds: "
        f"{namespace}/{metric_name}"
    )


def test_cloudwatch_metric_sink_writes_to_localstack() -> None:
    client = get_cloudwatch_client()

    suffix = uuid4().hex[:8]

    namespace = (
        f"RealStock/Integration/{suffix}"
    )

    metric_name = (
        "ObservabilityIntegrationMetric"
    )

    sink = CloudWatchMetricSink(
        namespace=namespace,
        client=client,
    )

    metric = MetricPoint(
        name=metric_name,
        value=1.0,
        unit=MetricUnit.COUNT,
        dimensions={
            "Environment": "integration",
            "Service": "observability",
        },
        timestamp=datetime.now(UTC),
    )

    sink.emit(metric)

    stored_metric = wait_for_metric(
        client=client,
        namespace=namespace,
        metric_name=metric_name,
    )

    assert (
        stored_metric["Namespace"]
        == namespace
    )

    assert (
        stored_metric["MetricName"]
        == metric_name
    )

    dimensions = {
        item["Name"]: item["Value"]
        for item in stored_metric.get(
            "Dimensions",
            [],
        )
    }

    assert dimensions == {
        "Environment": "integration",
        "Service": "observability",
    }