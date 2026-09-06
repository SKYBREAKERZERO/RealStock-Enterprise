from __future__ import annotations

from collections.abc import (
    Iterator,
    Mapping,
)
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import (
    UTC,
    datetime,
)
from enum import StrEnum
from threading import Lock
from time import perf_counter
from typing import Protocol


class MetricUnit(StrEnum):
    COUNT = "Count"
    MILLISECONDS = "Milliseconds"


@dataclass(
    frozen=True,
    slots=True,
)
class MetricPoint:
    name: str
    value: float
    unit: MetricUnit
    dimensions: dict[str, str]
    timestamp: datetime


class MetricSink(Protocol):
    """
    Backend contract for metrics delivery.

    Implementations may later write to:
    - CloudWatch PutMetricData
    - EMF
    - OpenTelemetry
    - Prometheus
    - an in-memory test sink
    """

    def emit(
        self,
        metric: MetricPoint,
    ) -> None:
        ...


class NoopMetricSink:
    """
    Production-safe default when metrics are not configured.

    This keeps observability optional at application
    construction boundaries and avoids coupling business
    services to a concrete monitoring backend.
    """

    def emit(
        self,
        metric: MetricPoint,
    ) -> None:
        del metric


class InMemoryMetricSink:
    """
    Deterministic metric sink used by unit and integration
    tests.
    """

    def __init__(self) -> None:
        self._metrics: list[
            MetricPoint
        ] = []

        self._lock = Lock()

    def emit(
        self,
        metric: MetricPoint,
    ) -> None:
        with self._lock:
            self._metrics.append(
                metric
            )

    @property
    def metrics(
        self,
    ) -> tuple[MetricPoint, ...]:
        with self._lock:
            return tuple(
                self._metrics
            )

    def clear(self) -> None:
        with self._lock:
            self._metrics.clear()


class MetricsRecorder:
    """
    Application-facing metric recorder.

    Business and transport services depend on this class,
    not on CloudWatch or another vendor-specific API.
    """

    def __init__(
        self,
        *,
        sink: MetricSink | None = None,
        default_dimensions: (
            Mapping[str, str] | None
        ) = None,
    ) -> None:
        self._sink = (
            sink
            if sink is not None
            else NoopMetricSink()
        )

        self._default_dimensions = (
            self._normalize_dimensions(
                default_dimensions
            )
        )

    @staticmethod
    def _normalize_name(
        name: str,
    ) -> str:
        normalized = name.strip()

        if not normalized:
            raise ValueError(
                "metric name must not be empty"
            )

        return normalized

    @staticmethod
    def _normalize_dimensions(
        dimensions: (
            Mapping[str, str] | None
        ),
    ) -> dict[str, str]:
        if dimensions is None:
            return {}

        result: dict[str, str] = {}

        for key, value in (
            dimensions.items()
        ):
            normalized_key = (
                key.strip()
            )

            normalized_value = (
                value.strip()
            )

            if not normalized_key:
                raise ValueError(

                        "metric dimension name "
                        "must not be empty"

                )

            if not normalized_value:
                raise ValueError(

                        "metric dimension value "
                        "must not be empty"

                )

            result[
                normalized_key
            ] = normalized_value

        return result

    def _merge_dimensions(
        self,
        dimensions: (
            Mapping[str, str] | None
        ),
    ) -> dict[str, str]:
        merged = dict(
            self._default_dimensions
        )

        merged.update(
            self._normalize_dimensions(
                dimensions
            )
        )

        return merged

    def record(
        self,
        name: str,
        value: float,
        *,
        unit: MetricUnit,
        dimensions: (
            Mapping[str, str] | None
        ) = None,
    ) -> None:
        metric_name = (
            self._normalize_name(
                name
            )
        )

        metric = MetricPoint(
            name=metric_name,
            value=float(value),
            unit=unit,
            dimensions=(
                self._merge_dimensions(
                    dimensions
                )
            ),
            timestamp=(
                datetime.now(
                    UTC
                )
            ),
        )

        self._sink.emit(
            metric
        )

    def increment(
        self,
        name: str,
        *,
        value: float = 1.0,
        dimensions: (
            Mapping[str, str] | None
        ) = None,
    ) -> None:
        self.record(
            name,
            value,
            unit=MetricUnit.COUNT,
            dimensions=dimensions,
        )

    def record_milliseconds(
        self,
        name: str,
        value: float,
        *,
        dimensions: (
            Mapping[str, str] | None
        ) = None,
    ) -> None:
        self.record(
            name,
            value,
            unit=(
                MetricUnit.MILLISECONDS
            ),
            dimensions=dimensions,
        )

    @contextmanager
    def timer(
        self,
        name: str,
        *,
        dimensions: (
            Mapping[str, str] | None
        ) = None,
    ) -> Iterator[None]:
        start = perf_counter()

        try:
            yield

        finally:
            elapsed_ms = (
                perf_counter()
                - start
            ) * 1000.0

            self.record_milliseconds(
                name,
                elapsed_ms,
                dimensions=dimensions,
            )