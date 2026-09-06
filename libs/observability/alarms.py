from __future__ import annotations

import math
from collections.abc import (
    Mapping,
)
from dataclasses import (
    dataclass,
    field,
)
from enum import StrEnum
from types import MappingProxyType

from botocore.client import BaseClient

from libs.observability.cloudwatch import (
    DEFAULT_METRIC_NAMESPACE,
)
from libs.observability.metrics import (
    MetricUnit,
)


class AlarmStatistic(StrEnum):
    AVERAGE = "Average"
    SUM = "Sum"
    MINIMUM = "Minimum"
    MAXIMUM = "Maximum"
    SAMPLE_COUNT = "SampleCount"


class AlarmComparisonOperator(StrEnum):
    GREATER_THAN_OR_EQUAL = (
        "GreaterThanOrEqualToThreshold"
    )
    GREATER_THAN = (
        "GreaterThanThreshold"
    )
    LESS_THAN = (
        "LessThanThreshold"
    )
    LESS_THAN_OR_EQUAL = (
        "LessThanOrEqualToThreshold"
    )


class TreatMissingData(StrEnum):
    BREACHING = "breaching"
    NOT_BREACHING = "notBreaching"
    IGNORE = "ignore"
    MISSING = "missing"


@dataclass(
    frozen=True,
    slots=True,
)
class AlarmDefinition:
    """
    Vendor-facing configuration for one CloudWatch
    metric alarm.

    This object contains alarm policy only. It does not
    perform AWS API calls itself.
    """

    name: str
    metric_name: str
    threshold: float
    comparison_operator: (
        AlarmComparisonOperator
    )

    namespace: str = (
        DEFAULT_METRIC_NAMESPACE
    )

    statistic: AlarmStatistic = (
        AlarmStatistic.SUM
    )

    period_seconds: int = 60

    evaluation_periods: int = 1

    datapoints_to_alarm: int | None = (
        None
    )

    dimensions: Mapping[
        str,
        str,
    ] = field(
        default_factory=dict
    )

    unit: MetricUnit | None = None

    treat_missing_data: (
        TreatMissingData
    ) = (
        TreatMissingData.NOT_BREACHING
    )

    alarm_actions: tuple[
        str,
        ...,
    ] = ()

    description: str | None = None

    actions_enabled: bool = True

    def __post_init__(
        self,
    ) -> None:
        name = self.name.strip()

        if not name:
            raise ValueError(
                "alarm name must not be empty"
            )

        metric_name = (
            self.metric_name.strip()
        )

        if not metric_name:
            raise ValueError(
                "metric name must not be empty"
            )

        namespace = (
            self.namespace.strip()
        )

        if not namespace:
            raise ValueError(
                "namespace must not be empty"
            )

        threshold = float(
            self.threshold
        )

        if not math.isfinite(
            threshold
        ):
            raise ValueError(
                "threshold must be finite"
            )

        if self.period_seconds <= 0:
            raise ValueError(
                "period_seconds must be positive"
            )

        if self.evaluation_periods <= 0:
            raise ValueError(
                "evaluation_periods must be positive"
            )

        datapoints_to_alarm = (
            self.datapoints_to_alarm
        )

        if (
            datapoints_to_alarm
            is not None
        ):
            if datapoints_to_alarm <= 0:
                raise ValueError(
                    "datapoints_to_alarm "
                    "must be positive"
                )

            if (
                datapoints_to_alarm
                > self.evaluation_periods
            ):
                raise ValueError(
                    "datapoints_to_alarm "
                    "must not exceed "
                    "evaluation_periods"
                )

        normalized_dimensions: dict[
            str,
            str,
        ] = {}

        for key, value in (
            self.dimensions.items()
        ):
            normalized_key = (
                str(key).strip()
            )

            normalized_value = (
                str(value).strip()
            )

            if not normalized_key:
                raise ValueError(
                    "alarm dimension name "
                    "must not be empty"
                )

            if not normalized_value:
                raise ValueError(
                    "alarm dimension value "
                    "must not be empty"
                )

            normalized_dimensions[
                normalized_key
            ] = normalized_value

        normalized_actions: list[
            str
        ] = []

        for action in (
            self.alarm_actions
        ):
            normalized_action = (
                action.strip()
            )

            if not normalized_action:
                raise ValueError(
                    "alarm action ARN "
                    "must not be empty"
                )

            normalized_actions.append(
                normalized_action
            )

        description = (
            self.description.strip()
            if self.description
            is not None
            else None
        )

        if description == "":
            description = None

        object.__setattr__(
            self,
            "name",
            name,
        )

        object.__setattr__(
            self,
            "metric_name",
            metric_name,
        )

        object.__setattr__(
            self,
            "namespace",
            namespace,
        )

        object.__setattr__(
            self,
            "threshold",
            threshold,
        )

        object.__setattr__(
            self,
            "dimensions",
            MappingProxyType(
                normalized_dimensions
            ),
        )

        object.__setattr__(
            self,
            "alarm_actions",
            tuple(
                normalized_actions
            ),
        )

        object.__setattr__(
            self,
            "description",
            description,
        )


class CloudWatchAlarmManager:
    """
    Thin AWS adapter for CloudWatch metric alarms.

    Provisioning failures deliberately propagate to the
    caller. Alarm configuration is control-plane work and
    must not silently fail.
    """

    def __init__(
        self,
        *,
        client: BaseClient,
    ) -> None:
        self._client = client

    def put_alarm(
        self,
        alarm: AlarmDefinition,
    ) -> None:
        request: dict[
            str,
            object,
        ] = {
            "AlarmName":
                alarm.name,
            "ActionsEnabled":
                alarm.actions_enabled,
            "MetricName":
                alarm.metric_name,
            "Namespace":
                alarm.namespace,
            "Statistic":
                alarm.statistic.value,
            "Period":
                alarm.period_seconds,
            "EvaluationPeriods":
                alarm.evaluation_periods,
            "Threshold":
                alarm.threshold,
            "ComparisonOperator": (
                alarm
                .comparison_operator
                .value
            ),
            "TreatMissingData": (
                alarm
                .treat_missing_data
                .value
            ),
        }

        if alarm.dimensions:
            request[
                "Dimensions"
            ] = [
                {
                    "Name": name,
                    "Value": value,
                }
                for name, value
                in sorted(
                    alarm
                    .dimensions
                    .items()
                )
            ]

        if (
            alarm.datapoints_to_alarm
            is not None
        ):
            request[
                "DatapointsToAlarm"
            ] = (
                alarm
                .datapoints_to_alarm
            )

        if alarm.unit is not None:
            request["Unit"] = (
                alarm.unit.value
            )

        if alarm.alarm_actions:
            request[
                "AlarmActions"
            ] = list(
                alarm.alarm_actions
            )

        if (
            alarm.description
            is not None
        ):
            request[
                "AlarmDescription"
            ] = (
                alarm.description
            )

        self._client.put_metric_alarm(
            **request
        )

    def delete_alarm(
        self,
        alarm_name: str,
    ) -> None:
        normalized_name = (
            alarm_name.strip()
        )

        if not normalized_name:
            raise ValueError(
                "alarm name must not be empty"
            )

        self._client.delete_alarms(
            AlarmNames=[
                normalized_name
            ]
        )