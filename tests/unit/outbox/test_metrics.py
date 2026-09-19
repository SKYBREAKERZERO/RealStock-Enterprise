from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

from libs.database.repositories.outbox import (
    OutboxBacklogSnapshot,
)
from services.outbox_dispatcher.dispatcher import (
    DispatchResult,
)
from services.outbox_dispatcher.metrics import (
    CloudWatchOutboxMetrics,
    NoOpOutboxMetrics,
)

pytestmark = pytest.mark.unit


def _metrics(
    client: MagicMock,
) -> CloudWatchOutboxMetrics:
    return CloudWatchOutboxMetrics(
        namespace="RealStock/Outbox",
        environment="test",
        service_name="outbox-dispatcher",
        client=client,
    )


def _metric_map(
    client: MagicMock,
) -> dict[str, dict[str, object]]:
    call = (
        client
        .put_metric_data
        .call_args
    )

    assert call is not None

    metric_data = (
        call.kwargs[
            "MetricData"
        ]
    )

    return {
        str(
            metric[
                "MetricName"
            ]
        ): metric
        for metric in metric_data
    }


def test_record_dispatch_publishes_batch_metrics() -> None:
    client = MagicMock()

    metrics = _metrics(
        client
    )

    result = DispatchResult(
        claimed=3,
        published=2,
        failed=1,
    )

    metrics.record_dispatch(
        result=result,
        duration_ms=125.5,
    )

    client.put_metric_data.assert_called_once()

    call = (
        client
        .put_metric_data
        .call_args
    )

    assert call is not None

    assert (
        call.kwargs[
            "Namespace"
        ]
        == "RealStock/Outbox"
    )

    metric_map = _metric_map(
        client
    )

    assert (
        metric_map[
            "OutboxClaimedCount"
        ]["Value"]
        == 3.0
    )

    assert (
        metric_map[
            "OutboxClaimedCount"
        ]["Unit"]
        == "Count"
    )

    assert (
        metric_map[
            "OutboxPublishSuccessCount"
        ]["Value"]
        == 2.0
    )

    assert (
        metric_map[
            "OutboxPublishFailureCount"
        ]["Value"]
        == 1.0
    )

    assert (
        metric_map[
            "OutboxDispatchDurationMilliseconds"
        ]["Value"]
        == 125.5
    )

    assert (
        metric_map[
            "OutboxDispatchDurationMilliseconds"
        ]["Unit"]
        == "Milliseconds"
    )


def test_metrics_use_low_cardinality_dimensions() -> None:
    client = MagicMock()

    metrics = _metrics(
        client
    )

    metrics.record_worker_error()

    metric_map = _metric_map(
        client
    )

    datum = metric_map[
        "OutboxWorkerErrorCount"
    ]

    assert datum[
        "Dimensions"
    ] == [
        {
            "Name": "Environment",
            "Value": "test",
        },
        {
            "Name": "Service",
            "Value": "outbox-dispatcher",
        },
    ]


def test_record_backlog_publishes_pending_count_and_age() -> None:
    client = MagicMock()

    metrics = _metrics(
        client
    )

    observed_at = datetime(
        2026,
        9,
        19,
        12,
        0,
        0,
        tzinfo=UTC,
    )

    snapshot = OutboxBacklogSnapshot(
        pending_count=7,
        oldest_pending_at=(
            observed_at
            - timedelta(
                minutes=5
            )
        ),
    )

    metrics.record_backlog(
        snapshot=snapshot,
        observed_at=observed_at,
    )

    metric_map = _metric_map(
        client
    )

    assert (
        metric_map[
            "OutboxPendingCount"
        ]["Value"]
        == 7.0
    )

    assert (
        metric_map[
            "OutboxPendingCount"
        ]["Unit"]
        == "Count"
    )

    assert (
        metric_map[
            "OutboxOldestPendingAgeSeconds"
        ]["Value"]
        == 300.0
    )

    assert (
        metric_map[
            "OutboxOldestPendingAgeSeconds"
        ]["Unit"]
        == "Seconds"
    )


def test_empty_backlog_reports_zero_age() -> None:
    client = MagicMock()

    metrics = _metrics(
        client
    )

    snapshot = OutboxBacklogSnapshot(
        pending_count=0,
        oldest_pending_at=None,
    )

    metrics.record_backlog(
        snapshot=snapshot,
        observed_at=datetime(
            2026,
            9,
            19,
            12,
            0,
            tzinfo=UTC,
        ),
    )

    metric_map = _metric_map(
        client
    )

    assert (
        metric_map[
            "OutboxPendingCount"
        ]["Value"]
        == 0.0
    )

    assert (
        metric_map[
            "OutboxOldestPendingAgeSeconds"
        ]["Value"]
        == 0.0
    )


def test_future_oldest_pending_time_is_clamped_to_zero() -> None:
    client = MagicMock()

    metrics = _metrics(
        client
    )

    observed_at = datetime(
        2026,
        9,
        19,
        12,
        0,
        tzinfo=UTC,
    )

    snapshot = OutboxBacklogSnapshot(
        pending_count=1,
        oldest_pending_at=(
            observed_at
            + timedelta(
                seconds=30
            )
        ),
    )

    metrics.record_backlog(
        snapshot=snapshot,
        observed_at=observed_at,
    )

    metric_map = _metric_map(
        client
    )

    assert (
        metric_map[
            "OutboxOldestPendingAgeSeconds"
        ]["Value"]
        == 0.0
    )


def test_worker_error_records_one_count() -> None:
    client = MagicMock()

    metrics = _metrics(
        client
    )

    metrics.record_worker_error()

    metric_map = _metric_map(
        client
    )

    assert (
        metric_map[
            "OutboxWorkerErrorCount"
        ]["Value"]
        == 1.0
    )

    assert (
        metric_map[
            "OutboxWorkerErrorCount"
        ]["Unit"]
        == "Count"
    )


def test_negative_dispatch_duration_is_rejected() -> None:
    client = MagicMock()

    metrics = _metrics(
        client
    )

    result = DispatchResult(
        claimed=1,
        published=1,
        failed=0,
    )

    with pytest.raises(
        ValueError,
        match=(
            "duration_ms must not "
            "be negative"
        ),
    ):
        metrics.record_dispatch(
            result=result,
            duration_ms=-1.0,
        )

    client.put_metric_data.assert_not_called()


def test_backlog_rejects_naive_observation_time() -> None:
    client = MagicMock()

    metrics = _metrics(
        client
    )

    snapshot = OutboxBacklogSnapshot(
        pending_count=0,
        oldest_pending_at=None,
    )

    with pytest.raises(
        ValueError,
        match=(
            "datetime must be "
            "timezone-aware"
        ),
    ):
        metrics.record_backlog(
            snapshot=snapshot,
            observed_at=datetime(
                2026,
                9,
                19,
                12,
                0,
            ),
        )

    client.put_metric_data.assert_not_called()


def test_backlog_rejects_naive_oldest_pending_time() -> None:
    client = MagicMock()

    metrics = _metrics(
        client
    )

    snapshot = OutboxBacklogSnapshot(
        pending_count=1,
        oldest_pending_at=datetime(
            2026,
            9,
            19,
            11,
            55,
        ),
    )

    with pytest.raises(
        ValueError,
        match=(
            "datetime must be "
            "timezone-aware"
        ),
    ):
        metrics.record_backlog(
            snapshot=snapshot,
            observed_at=datetime(
                2026,
                9,
                19,
                12,
                0,
                tzinfo=UTC,
            ),
        )

    client.put_metric_data.assert_not_called()


@pytest.mark.parametrize(
    ("field", "kwargs"),
    [
        (
            "namespace",
            {
                "namespace": " ",
                "environment": "test",
                "service_name": (
                    "outbox-dispatcher"
                ),
            },
        ),
        (
            "environment",
            {
                "namespace": (
                    "RealStock/Outbox"
                ),
                "environment": " ",
                "service_name": (
                    "outbox-dispatcher"
                ),
            },
        ),
        (
            "service_name",
            {
                "namespace": (
                    "RealStock/Outbox"
                ),
                "environment": "test",
                "service_name": " ",
            },
        ),
    ],
)
def test_metrics_configuration_must_not_be_empty(
    field: str,
    kwargs: dict[str, str],
) -> None:
    client = MagicMock()

    with pytest.raises(
        ValueError,
        match=(
            f"{field} must not be empty"
        ),
    ):
        CloudWatchOutboxMetrics(
            **kwargs,
            client=client,
        )


def test_noop_metrics_accept_runtime_calls() -> None:
    metrics = NoOpOutboxMetrics()

    result = DispatchResult(
        claimed=1,
        published=1,
        failed=0,
    )

    snapshot = OutboxBacklogSnapshot(
        pending_count=0,
        oldest_pending_at=None,
    )

    metrics.record_dispatch(
        result=result,
        duration_ms=10.0,
    )

    metrics.record_backlog(
        snapshot=snapshot,
        observed_at=datetime.now(
            UTC
        ),
    )

    metrics.record_worker_error()