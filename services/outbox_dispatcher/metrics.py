from __future__ import annotations

from datetime import UTC, datetime
from typing import Protocol

from botocore.client import BaseClient

from libs.aws import get_cloudwatch_client
from libs.database.repositories.outbox import (
    OutboxBacklogSnapshot,
)
from services.outbox_dispatcher.dispatcher import (
    DispatchResult,
)

DEFAULT_METRICS_NAMESPACE = "RealStock/Outbox"
DEFAULT_SERVICE_NAME = "outbox-dispatcher"

METRIC_CLAIMED_COUNT = "OutboxClaimedCount"
METRIC_PUBLISH_SUCCESS_COUNT = (
    "OutboxPublishSuccessCount"
)
METRIC_PUBLISH_FAILURE_COUNT = (
    "OutboxPublishFailureCount"
)
METRIC_DISPATCH_DURATION_MS = (
    "OutboxDispatchDurationMilliseconds"
)
METRIC_PENDING_COUNT = "OutboxPendingCount"
METRIC_OLDEST_PENDING_AGE_SECONDS = (
    "OutboxOldestPendingAgeSeconds"
)
METRIC_WORKER_ERROR_COUNT = (
    "OutboxWorkerErrorCount"
)


class OutboxMetrics(Protocol):
    """
    Observability contract used by the outbox worker runtime.

    Implementations must not influence dispatcher delivery
    semantics.
    """

    def record_dispatch(
        self,
        *,
        result: DispatchResult,
        duration_ms: float,
    ) -> None: ...

    def record_backlog(
        self,
        *,
        snapshot: OutboxBacklogSnapshot,
        observed_at: datetime | None = None,
    ) -> None: ...

    def record_worker_error(
        self,
    ) -> None: ...


class NoOpOutboxMetrics:
    """
    Metrics implementation that intentionally performs no I/O.

    Useful for:
    - unit tests;
    - environments where external metrics are disabled.
    """

    def record_dispatch(
        self,
        *,
        result: DispatchResult,
        duration_ms: float,
    ) -> None:
        del result
        del duration_ms

    def record_backlog(
        self,
        *,
        snapshot: OutboxBacklogSnapshot,
        observed_at: datetime | None = None,
    ) -> None:
        del snapshot
        del observed_at

    def record_worker_error(
        self,
    ) -> None:
        return None


class CloudWatchOutboxMetrics:
    """
    Publish outbox operational metrics to Amazon CloudWatch.

    Metric dimensions deliberately remain low-cardinality.

    Worker IDs are not included as dimensions because ECS tasks
    are ephemeral and would create unbounded metric cardinality.
    """

    def __init__(
        self,
        *,
        namespace: str = DEFAULT_METRICS_NAMESPACE,
        environment: str,
        service_name: str = DEFAULT_SERVICE_NAME,
        client: BaseClient | None = None,
    ) -> None:
        normalized_namespace = (
            namespace.strip()
        )

        normalized_environment = (
            environment.strip()
        )

        normalized_service_name = (
            service_name.strip()
        )

        if not normalized_namespace:
            raise ValueError(
                "namespace must not be empty"
            )

        if not normalized_environment:
            raise ValueError(
                "environment must not be empty"
            )

        if not normalized_service_name:
            raise ValueError(
                "service_name must not be empty"
            )

        self._namespace = (
            normalized_namespace
        )

        self._environment = (
            normalized_environment
        )

        self._service_name = (
            normalized_service_name
        )

        self._client = (
            client
            if client is not None
            else get_cloudwatch_client()
        )

    @property
    def namespace(
        self,
    ) -> str:
        return self._namespace

    @property
    def environment(
        self,
    ) -> str:
        return self._environment

    @property
    def service_name(
        self,
    ) -> str:
        return self._service_name

    def record_dispatch(
        self,
        *,
        result: DispatchResult,
        duration_ms: float,
    ) -> None:
        """
        Record metrics for one completed dispatcher batch.

        This method should normally be called only when a batch
        actually claimed events. Idle polling is intentionally not
        emitted as dispatch telemetry.
        """

        if duration_ms < 0:
            raise ValueError(
                "duration_ms must not be negative"
            )

        if result.claimed < 0:
            raise ValueError(
                "claimed must not be negative"
            )

        if result.published < 0:
            raise ValueError(
                "published must not be negative"
            )

        if result.failed < 0:
            raise ValueError(
                "failed must not be negative"
            )

        self._client.put_metric_data(
            Namespace=self._namespace,
            MetricData=[
                self._metric(
                    name=METRIC_CLAIMED_COUNT,
                    value=result.claimed,
                    unit="Count",
                ),
                self._metric(
                    name=(
                        METRIC_PUBLISH_SUCCESS_COUNT
                    ),
                    value=result.published,
                    unit="Count",
                ),
                self._metric(
                    name=(
                        METRIC_PUBLISH_FAILURE_COUNT
                    ),
                    value=result.failed,
                    unit="Count",
                ),
                self._metric(
                    name=(
                        METRIC_DISPATCH_DURATION_MS
                    ),
                    value=duration_ms,
                    unit="Milliseconds",
                ),
            ],
        )

    def record_backlog(
        self,
        *,
        snapshot: OutboxBacklogSnapshot,
        observed_at: datetime | None = None,
    ) -> None:
        """
        Record durable unpublished-event backlog.

        Oldest pending age measures how long the oldest event has
        remained in the transactional outbox.

        When there is no backlog, age is emitted as zero so an
        existing CloudWatch alarm can return to OK state.
        """

        if snapshot.pending_count < 0:
            raise ValueError(
                "pending_count must not be negative"
            )

        effective_observed_at = (
            self._resolve_utc(
                observed_at
            )
        )

        oldest_pending_age_seconds = (
            self._oldest_pending_age_seconds(
                snapshot=snapshot,
                observed_at=(
                    effective_observed_at
                ),
            )
        )

        self._client.put_metric_data(
            Namespace=self._namespace,
            MetricData=[
                self._metric(
                    name=METRIC_PENDING_COUNT,
                    value=(
                        snapshot.pending_count
                    ),
                    unit="Count",
                ),
                self._metric(
                    name=(
                        METRIC_OLDEST_PENDING_AGE_SECONDS
                    ),
                    value=(
                        oldest_pending_age_seconds
                    ),
                    unit="Seconds",
                ),
            ],
        )

    def record_worker_error(
        self,
    ) -> None:
        """
        Record one worker-level infrastructure/runtime failure.

        Examples:
        - PostgreSQL unavailable;
        - claim transaction failure;
        - unexpected worker-loop exception.

        EventBridge publication failures are represented separately
        by OutboxPublishFailureCount.
        """

        self._client.put_metric_data(
            Namespace=self._namespace,
            MetricData=[
                self._metric(
                    name=(
                        METRIC_WORKER_ERROR_COUNT
                    ),
                    value=1,
                    unit="Count",
                )
            ],
        )

    def _metric(
        self,
        *,
        name: str,
        value: int | float,
        unit: str,
    ) -> dict[str, object]:
        return {
            "MetricName": name,
            "Dimensions": [
                {
                    "Name": "Environment",
                    "Value": (
                        self._environment
                    ),
                },
                {
                    "Name": "Service",
                    "Value": (
                        self._service_name
                    ),
                },
            ],
            "Value": float(
                value
            ),
            "Unit": unit,
        }

    @classmethod
    def _oldest_pending_age_seconds(
        cls,
        *,
        snapshot: OutboxBacklogSnapshot,
        observed_at: datetime,
    ) -> float:
        oldest_pending_at = (
            snapshot.oldest_pending_at
        )

        if oldest_pending_at is None:
            return 0.0

        normalized_oldest_pending_at = (
            cls._resolve_utc(
                oldest_pending_at
            )
        )

        age_seconds = (
            observed_at
            - normalized_oldest_pending_at
        ).total_seconds()

        return max(
            age_seconds,
            0.0,
        )

    @staticmethod
    def _resolve_utc(
        value: datetime | None,
    ) -> datetime:
        if value is None:
            return datetime.now(
                UTC
            )

        if value.tzinfo is None:
            raise ValueError(
                "datetime must be timezone-aware"
            )

        return value.astimezone(
            UTC
        )