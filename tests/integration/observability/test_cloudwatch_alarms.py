from __future__ import annotations

import time
from uuid import uuid4

import pytest

from libs.aws import (
    get_cloudwatch_client,
)
from libs.observability import (
    AlarmComparisonOperator,
    AlarmDefinition,
    AlarmStatistic,
    CloudWatchAlarmManager,
    MetricUnit,
    TreatMissingData,
)

pytestmark = pytest.mark.integration


def wait_for_alarm(
    *,
    client,
    alarm_name: str,
) -> dict:
    for _ in range(20):
        response = (
            client.describe_alarms(
                AlarmNames=[
                    alarm_name
                ]
            )
        )

        alarms = response.get(
            "MetricAlarms",
            [],
        )

        if alarms:
            return alarms[0]

        time.sleep(
            0.25
        )

    raise AssertionError(
        "CloudWatch alarm was not "
        "created"
    )


def test_cloudwatch_alarm_manager_writes_to_localstack() -> None:
    cloudwatch = (
        get_cloudwatch_client()
    )

    suffix = uuid4().hex[:8]

    alarm_name = (
        f"realstock-test-risk-"
        f"failures-{suffix}"
    )

    namespace = (
        f"RealStock/Integration/"
        f"{suffix}"
    )

    manager = (
        CloudWatchAlarmManager(
            client=cloudwatch
        )
    )

    alarm = AlarmDefinition(
        name=alarm_name,
        description=(
            "Integration test alarm"
        ),
        metric_name=(
            "RiskProcessingFailures"
        ),
        namespace=namespace,
        statistic=(
            AlarmStatistic.SUM
        ),
        threshold=5,
        comparison_operator=(
            AlarmComparisonOperator
            .GREATER_THAN_OR_EQUAL
        ),
        period_seconds=60,
        evaluation_periods=2,
        datapoints_to_alarm=1,
        dimensions={
            "Service":
                "risk-engine",
            "Environment":
                "local",
        },
        unit=MetricUnit.COUNT,
        treat_missing_data=(
            TreatMissingData
            .NOT_BREACHING
        ),
    )

    try:
        manager.put_alarm(
            alarm
        )

        actual = wait_for_alarm(
            client=cloudwatch,
            alarm_name=alarm_name,
        )

        assert (
            actual[
                "AlarmName"
            ]
            == alarm_name
        )

        assert (
            actual[
                "AlarmDescription"
            ]
            == "Integration test alarm"
        )

        assert (
            actual[
                "MetricName"
            ]
            == "RiskProcessingFailures"
        )

        assert (
            actual[
                "Namespace"
            ]
            == namespace
        )

        assert (
            actual[
                "Statistic"
            ]
            == "Sum"
        )

        assert (
            actual[
                "Period"
            ]
            == 60
        )

        assert (
            actual[
                "EvaluationPeriods"
            ]
            == 2
        )

        assert (
            actual[
                "DatapointsToAlarm"
            ]
            == 1
        )

        assert (
            actual[
                "Threshold"
            ]
            == pytest.approx(
                5.0
            )
        )

        assert (
            actual[
                "ComparisonOperator"
            ]
            == (
                "GreaterThanOrEqual"
                "ToThreshold"
            )
        )

        assert (
            actual[
                "TreatMissingData"
            ]
            == "notBreaching"
        )

        assert (
            actual[
                "Unit"
            ]
            == "Count"
        )

        actual_dimensions = {
            dimension["Name"]:
                dimension["Value"]
            for dimension
            in actual.get(
                "Dimensions",
                [],
            )
        }

        assert actual_dimensions == {
            "Service":
                "risk-engine",
            "Environment":
                "local",
        }

    finally:
        try:
            manager.delete_alarm(
                alarm_name
            )
        except Exception:
            pass