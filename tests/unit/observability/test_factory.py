from __future__ import annotations

from typing import Any

import pytest

from libs.observability.factory import (
    create_cloudwatch_metrics_recorder,
)


class RecordingCloudWatchClient:
    def __init__(self) -> None:
        self.requests: list[
            dict[str, Any]
        ] = []

    def put_metric_data(
        self,
        **kwargs: Any,
    ) -> dict[str, Any]:
        self.requests.append(
            kwargs
        )

        return {}


class FailingCloudWatchClient:
    def put_metric_data(
        self,
        **kwargs: Any,
    ) -> dict[str, Any]:
        raise RuntimeError(
            "cloudwatch unavailable"
        )


def test_factory_adds_service_and_environment_dimensions() -> None:
    client = (
        RecordingCloudWatchClient()
    )

    recorder = (
        create_cloudwatch_metrics_recorder(
            service_name="risk-engine",
            environment="local",
            client=client,
        )
    )

    recorder.increment(
        "RiskProcessingFailures"
    )

    assert len(
        client.requests
    ) == 1

    metric_data = (
        client.requests[0][
            "MetricData"
        ][0]
    )

    dimensions = {
        item["Name"]:
            item["Value"]
        for item
        in metric_data[
            "Dimensions"
        ]
    }

    assert dimensions == {
        "Service": "risk-engine",
        "Environment": "local",
    }


def test_factory_merges_call_dimensions() -> None:
    client = (
        RecordingCloudWatchClient()
    )

    recorder = (
        create_cloudwatch_metrics_recorder(
            service_name="alert-worker",
            environment="local",
            client=client,
        )
    )

    recorder.increment(
        "SqsProcessingFailures",
        dimensions={
            "FailureStage": "ACK"
        },
    )

    metric_data = (
        client.requests[0][
            "MetricData"
        ][0]
    )

    dimensions = {
        item["Name"]:
            item["Value"]
        for item
        in metric_data[
            "Dimensions"
        ]
    }

    assert dimensions == {
        "Service": "alert-worker",
        "Environment": "local",
        "FailureStage": "ACK",
    }


def test_factory_supports_custom_namespace() -> None:
    client = (
        RecordingCloudWatchClient()
    )

    recorder = (
        create_cloudwatch_metrics_recorder(
            service_name="risk-engine",
            environment="staging",
            namespace=(
                "RealStock/Staging"
            ),
            client=client,
        )
    )

    recorder.increment(
        "MarketEventsProcessed"
    )

    assert (
        client.requests[0][
            "Namespace"
        ]
        == "RealStock/Staging"
    )


def test_factory_normalizes_values() -> None:
    client = (
        RecordingCloudWatchClient()
    )

    recorder = (
        create_cloudwatch_metrics_recorder(
            service_name=(
                "  risk-engine  "
            ),
            environment=(
                "  prod  "
            ),
            namespace=(
                "  RealStock/Applications  "
            ),
            client=client,
        )
    )

    recorder.increment(
        "RiskProcessingFailures"
    )

    request = client.requests[0]

    assert (
        request["Namespace"]
        == "RealStock/Applications"
    )

    dimensions = {
        item["Name"]:
            item["Value"]
        for item
        in request[
            "MetricData"
        ][0]["Dimensions"]
    }

    assert dimensions[
        "Service"
    ] == "risk-engine"

    assert dimensions[
        "Environment"
    ] == "prod"


@pytest.mark.parametrize(
    ("field_name", "kwargs"),
    [
        (
            "service_name",
            {
                "service_name": "   ",
                "environment": "local",
            },
        ),
        (
            "environment",
            {
                "service_name":
                    "risk-engine",
                "environment": " ",
            },
        ),
        (
            "namespace",
            {
                "service_name":
                    "risk-engine",
                "environment": "local",
                "namespace": " ",
            },
        ),
    ],
)
def test_factory_rejects_empty_required_values(
    field_name: str,
    kwargs: dict[str, str],
) -> None:
    with pytest.raises(
        ValueError,
        match=field_name,
    ):
        create_cloudwatch_metrics_recorder(
            **kwargs
        )


def test_factory_isolates_cloudwatch_failure() -> None:
    recorder = (
        create_cloudwatch_metrics_recorder(
            service_name="risk-engine",
            environment="local",
            client=(
                FailingCloudWatchClient()
            ),
        )
    )

    # CloudWatch failure must not escape into
    # the application business path.
    recorder.increment(
        "RiskProcessingFailures"
    )


def test_factory_uses_shared_cloudwatch_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = (
        RecordingCloudWatchClient()
    )

    def fake_get_cloudwatch_client():
        return client

    monkeypatch.setattr(
        "libs.observability.factory."
        "get_cloudwatch_client",
        fake_get_cloudwatch_client,
    )

    recorder = (
        create_cloudwatch_metrics_recorder(
            service_name="risk-engine",
            environment="local",
        )
    )

    recorder.increment(
        "RiskProcessingFailures"
    )

    assert len(
        client.requests
    ) == 1