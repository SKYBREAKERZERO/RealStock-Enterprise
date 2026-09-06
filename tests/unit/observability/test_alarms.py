from __future__ import annotations

from unittest.mock import Mock

import pytest

from libs.observability import (
    AlarmComparisonOperator,
    AlarmDefinition,
    AlarmStatistic,
    CloudWatchAlarmManager,
    MetricUnit,
    TreatMissingData,
)


def build_alarm(
    **overrides,
) -> AlarmDefinition:
    values = {
        "name":
            "RiskProcessingFailuresHigh",
        "metric_name":
            "RiskProcessingFailures",
        "threshold":
            5,
        "comparison_operator": (
            AlarmComparisonOperator
            .GREATER_THAN_OR_EQUAL
        ),
    }

    values.update(
        overrides
    )

    return AlarmDefinition(
        **values
    )


def test_alarm_manager_maps_required_fields() -> None:
    client = Mock()

    manager = CloudWatchAlarmManager(
        client=client
    )

    alarm = build_alarm()

    manager.put_alarm(
        alarm
    )

    client.put_metric_alarm.assert_called_once_with(
        AlarmName=(
            "RiskProcessingFailuresHigh"
        ),
        ActionsEnabled=True,
        MetricName=(
            "RiskProcessingFailures"
        ),
        Namespace=(
            "RealStock/Applications"
        ),
        Statistic="Sum",
        Period=60,
        EvaluationPeriods=1,
        Threshold=5.0,
        ComparisonOperator=(
            "GreaterThanOrEqualToThreshold"
        ),
        TreatMissingData=(
            "notBreaching"
        ),
    )


def test_alarm_manager_maps_dimensions() -> None:
    client = Mock()

    manager = CloudWatchAlarmManager(
        client=client
    )

    alarm = build_alarm(
        dimensions={
            "Service":
                "risk-engine",
            "Environment":
                "local",
        }
    )

    manager.put_alarm(
        alarm
    )

    request = (
        client
        .put_metric_alarm
        .call_args
        .kwargs
    )

    assert request[
        "Dimensions"
    ] == [
        {
            "Name": "Environment",
            "Value": "local",
        },
        {
            "Name": "Service",
            "Value": "risk-engine",
        },
    ]


def test_alarm_manager_maps_optional_fields() -> None:
    client = Mock()

    manager = CloudWatchAlarmManager(
        client=client
    )

    alarm = build_alarm(
        statistic=(
            AlarmStatistic.AVERAGE
        ),
        period_seconds=300,
        evaluation_periods=3,
        datapoints_to_alarm=2,
        unit=(
            MetricUnit.MILLISECONDS
        ),
        description=(
            "Risk processing latency "
            "is elevated"
        ),
        alarm_actions=(
            "arn:aws:sns:"
            "ap-northeast-1:"
            "123456789012:"
            "realstock-alarm",
        ),
        treat_missing_data=(
            TreatMissingData.MISSING
        ),
    )

    manager.put_alarm(
        alarm
    )

    request = (
        client
        .put_metric_alarm
        .call_args
        .kwargs
    )

    assert request[
        "Statistic"
    ] == "Average"

    assert request[
        "Period"
    ] == 300

    assert request[
        "EvaluationPeriods"
    ] == 3

    assert request[
        "DatapointsToAlarm"
    ] == 2

    assert request[
        "Unit"
    ] == "Milliseconds"

    assert request[
        "TreatMissingData"
    ] == "missing"

    assert request[
        "AlarmActions"
    ] == [
        "arn:aws:sns:"
        "ap-northeast-1:"
        "123456789012:"
        "realstock-alarm"
    ]

    assert request[
        "AlarmDescription"
    ] == (
        "Risk processing latency "
        "is elevated"
    )


def test_alarm_definition_normalizes_values() -> None:
    alarm = build_alarm(
        name=(
            "  RiskFailuresHigh  "
        ),
        metric_name=(
            "  RiskProcessingFailures  "
        ),
        namespace=(
            "  RealStock/Test  "
        ),
        dimensions={
            " Service ":
                " risk-engine "
        },
    )

    assert (
        alarm.name
        == "RiskFailuresHigh"
    )

    assert (
        alarm.metric_name
        == "RiskProcessingFailures"
    )

    assert (
        alarm.namespace
        == "RealStock/Test"
    )

    assert dict(
        alarm.dimensions
    ) == {
        "Service":
            "risk-engine"
    }


@pytest.mark.parametrize(
    "field,value",
    [
        (
            "name",
            "   ",
        ),
        (
            "metric_name",
            "",
        ),
        (
            "namespace",
            " ",
        ),
    ],
)
def test_alarm_definition_rejects_empty_identifiers(
    field: str,
    value: str,
) -> None:
    with pytest.raises(
        ValueError
    ):
        build_alarm(
            **{
                field: value
            }
        )


@pytest.mark.parametrize(
    "threshold",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
    ],
)
def test_alarm_definition_rejects_non_finite_threshold(
    threshold: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="threshold must be finite",
    ):
        build_alarm(
            threshold=threshold
        )


def test_alarm_definition_rejects_invalid_period() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "period_seconds "
            "must be positive"
        ),
    ):
        build_alarm(
            period_seconds=0
        )


def test_alarm_definition_rejects_invalid_evaluation_periods() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "evaluation_periods "
            "must be positive"
        ),
    ):
        build_alarm(
            evaluation_periods=0
        )


def test_alarm_definition_rejects_datapoints_above_evaluation_periods() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "datapoints_to_alarm "
            "must not exceed "
            "evaluation_periods"
        ),
    ):
        build_alarm(
            evaluation_periods=2,
            datapoints_to_alarm=3,
        )


def test_alarm_definition_rejects_empty_dimension() -> None:
    with pytest.raises(
        ValueError,
        match=(
            "alarm dimension value "
            "must not be empty"
        ),
    ):
        build_alarm(
            dimensions={
                "Environment": " "
            }
        )


def test_alarm_dimensions_are_immutable() -> None:
    dimensions = {
        "Environment": "local"
    }

    alarm = build_alarm(
        dimensions=dimensions
    )

    dimensions[
        "Environment"
    ] = "prod"

    assert (
        alarm.dimensions[
            "Environment"
        ]
        == "local"
    )

    with pytest.raises(
        TypeError
    ):
        alarm.dimensions[
            "Environment"
        ] = "prod"  # type: ignore[index]


def test_alarm_manager_propagates_backend_failure() -> None:
    client = Mock()

    client.put_metric_alarm.side_effect = (
        RuntimeError(
            "cloudwatch unavailable"
        )
    )

    manager = CloudWatchAlarmManager(
        client=client
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "cloudwatch unavailable"
        ),
    ):
        manager.put_alarm(
            build_alarm()
        )


def test_alarm_manager_deletes_alarm() -> None:
    client = Mock()

    manager = CloudWatchAlarmManager(
        client=client
    )

    manager.delete_alarm(
        "RiskProcessingFailuresHigh"
    )

    client.delete_alarms.assert_called_once_with(
        AlarmNames=[
            "RiskProcessingFailuresHigh"
        ]
    )


def test_alarm_manager_rejects_empty_delete_name() -> None:
    client = Mock()

    manager = CloudWatchAlarmManager(
        client=client
    )

    with pytest.raises(
        ValueError
    ):
        manager.delete_alarm(
            " "
        )