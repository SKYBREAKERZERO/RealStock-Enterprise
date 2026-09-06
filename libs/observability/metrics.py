from __future__ import annotations

import logging
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
    """
    Vendor-neutral application metric.

    Business services emit MetricPoint objects without
    depending directly on CloudWatch, Prometheus,
    OpenTelemetry, or another monitoring backend.
    """

    name: str
    value: float
    unit: MetricUnit
    dimensions: dict[str, str]
    timestamp: datetime


class MetricSink(Protocol):
    """
    Backend contract for metric delivery.

    Implementations may write to:

    - AWS CloudWatch PutMetricData
    - CloudWatch Embedded Metric Format
    - OpenTelemetry
    - Prometheus
    - an in-memory test sink
    - a no-op sink
    """

    def emit(
        self,
        metric: MetricPoint,
    ) -> None:
        ...


class ResilientMetricSink:
    """
    Best-effort metric delivery wrapper.

    Telemetry backend failures are logged but are never
    propagated into the application business path.

    This prevents monitoring failures from changing
    business semantics such as:

    - SQS ACK / NO-ACK behavior
    - retry decisions
    - idempotency ownership
    - notification delivery
    - risk processing

    Example production composition:

        MetricsRecorder
            ↓
        ResilientMetricSink
            ↓
        CloudWatchMetricSink
            ↓
        AWS CloudWatch
    """

    def __init__(
        self,
        *,
        sink: MetricSink,
        logger: logging.Logger | None = None,
    ) -> None:
        self._sink = sink

        self._logger = (
            logger
            if logger is not None
            else logging.getLogger(
                __name__
            )
        )

    def emit(
        self,
        metric: MetricPoint,
    ) -> None:
        try:
            self._sink.emit(
                metric
            )

        except Exception:
            self._logger.exception(
                "metric emission failed",
                extra={
                    "structured_fields": {
                        "metric_name":
                            metric.name,
                        "metric_unit":
                            metric.unit.value,
                    }
                },
            )


class NoopMetricSink:
    """
    Safe default when metrics are not configured.

    This keeps observability optional at application
    construction boundaries and prevents business services
    from depending on a concrete monitoring backend.
    """

    def emit(
        self,
        metric: MetricPoint,
    ) -> None:
        del metric


class InMemoryMetricSink:
    """
    Deterministic thread-safe metric sink used by unit and
    integration tests.
    """

    def __init__(
        self,
    ) -> None:
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
        """
        Return an immutable snapshot of recorded metrics.
        """

        with self._lock:
            return tuple(
                self._metrics
            )

    def clear(
        self,
    ) -> None:
        with self._lock:
            self._metrics.clear()


class MetricsRecorder:
    """
    Application-facing metric recorder.

    Business and transport services depend on this class
    rather than on CloudWatch or another vendor-specific
    monitoring API.

    Responsibilities:

    - normalize metric names
    - normalize dimensions
    - merge default and call-level dimensions
    - create UTC timestamps
    - create MetricPoint objects
    - record counters
    - record millisecond latency
    - provide timer scopes

    Backend reliability belongs to MetricSink
    implementations such as ResilientMetricSink.
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
        """
        Return a new dictionary.

        Call-level dimensions override defaults without
        mutating either caller-owned dictionaries or the
        recorder's default dimensions.
        """

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
            value=float(
                value
            ),
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
        """
        Record a Count metric.

        The default increment value is 1.
        """

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
        """
        Record elapsed wall-clock duration in milliseconds.

        The latency metric is emitted even when the wrapped
        business operation raises an exception.

        When used with ResilientMetricSink, a telemetry
        backend failure cannot replace or hide the original
        business exception.
        """

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