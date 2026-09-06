from __future__ import annotations

from botocore.client import (
    BaseClient,
)

from libs.observability.metrics import (
    MetricPoint,
)

DEFAULT_METRIC_NAMESPACE = (
    "RealStock/Applications"
)


class CloudWatchMetricSink:
    """
    Translate application MetricPoint objects into
    CloudWatch PutMetricData requests.
    """

    def __init__(
        self,
        *,
        client: BaseClient,
        namespace: str = (
            DEFAULT_METRIC_NAMESPACE
        ),
    ) -> None:
        normalized_namespace = (
            namespace.strip()
        )

        if not normalized_namespace:
            raise ValueError(
                "namespace must not be empty"
            )

        self._client = client
        self._namespace = (
            normalized_namespace
        )

    def emit(
        self,
        metric: MetricPoint,
    ) -> None:
        metric_data = {
            "MetricName": metric.name,
            "Value": metric.value,
            "Unit": metric.unit.value,
            "Timestamp": metric.timestamp,
        }

        if metric.dimensions:
            metric_data[
                "Dimensions"
            ] = [
                {
                    "Name": name,
                    "Value": value,
                }
                for name, value
                in metric.dimensions.items()
            ]

        self._client.put_metric_data(
            Namespace=self._namespace,
            MetricData=[
                metric_data
            ],
        )