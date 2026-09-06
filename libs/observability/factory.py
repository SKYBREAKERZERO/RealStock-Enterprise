from __future__ import annotations

import logging

from botocore.client import BaseClient

from libs.aws import get_cloudwatch_client
from libs.observability.cloudwatch import (
    DEFAULT_METRIC_NAMESPACE,
    CloudWatchMetricSink,
)
from libs.observability.metrics import (
    MetricsRecorder,
    ResilientMetricSink,
)


def _normalize_required_value(
    value: str,
    *,
    field_name: str,
) -> str:
    normalized = value.strip()

    if not normalized:
        raise ValueError(
            f"{field_name} must not be empty"
        )

    return normalized


def create_cloudwatch_metrics_recorder(
    *,
    service_name: str,
    environment: str,
    namespace: str = DEFAULT_METRIC_NAMESPACE,
    client: BaseClient | None = None,
    logger: logging.Logger | None = None,
) -> MetricsRecorder:
    """
    Build the production CloudWatch metrics composition.

    Business services depend only on MetricsRecorder.

    Delivery path:

        MetricsRecorder
            ↓
        ResilientMetricSink
            ↓
        CloudWatchMetricSink
            ↓
        AWS CloudWatch

    Service and Environment are attached as stable,
    low-cardinality dimensions to every application metric.

    Telemetry backend failures are isolated by
    ResilientMetricSink and therefore cannot change
    business ACK, retry, idempotency, or notification
    semantics.
    """

    normalized_service = (
        _normalize_required_value(
            service_name,
            field_name="service_name",
        )
    )

    normalized_environment = (
        _normalize_required_value(
            environment,
            field_name="environment",
        )
    )

    normalized_namespace = (
        _normalize_required_value(
            namespace,
            field_name="namespace",
        )
    )

    cloudwatch_client = (
        client
        if client is not None
        else get_cloudwatch_client()
    )

    cloudwatch_sink = (
        CloudWatchMetricSink(
            client=cloudwatch_client,
            namespace=normalized_namespace,
        )
    )

    resilient_sink = (
        ResilientMetricSink(
            sink=cloudwatch_sink,
            logger=logger,
        )
    )

    return MetricsRecorder(
        sink=resilient_sink,
        default_dimensions={
            "Service": normalized_service,
            "Environment": normalized_environment,
        },
    )