from __future__ import annotations

from threading import Event
from unittest.mock import MagicMock

import pytest

from libs.database.repositories.outbox import (
    OutboxBacklogSnapshot,
)
from services.outbox_dispatcher.dispatcher import (
    DispatchResult,
)
from services.outbox_dispatcher.runner import (
    OutboxRunner,
)

pytestmark = pytest.mark.unit


class FakeClock:
    def __init__(
        self,
        *values: float,
    ) -> None:
        self._values = list(
            values
        )

        self._last = (
            self._values[-1]
            if self._values
            else 0.0
        )

    def __call__(
        self,
    ) -> float:
        if self._values:
            self._last = (
                self._values.pop(0)
            )

        return self._last


class RecordingStopEvent:
    def __init__(
        self,
    ) -> None:
        self.wait_calls: list[float | None] = []
        self._is_set = False

    def is_set(
        self,
    ) -> bool:
        return self._is_set

    def wait(
        self,
        timeout: float | None = None,
    ) -> bool:
        self.wait_calls.append(
            timeout
        )

        return self._is_set

    def set(
        self,
    ) -> None:
        self._is_set = True


def _runner(
    *,
    dispatcher: MagicMock | None = None,
    backlog_provider: MagicMock | None = None,
    metrics: MagicMock | None = None,
    stop_event: RecordingStopEvent | None = None,
    clock: FakeClock | None = None,
) -> tuple[
    OutboxRunner,
    MagicMock,
    MagicMock,
    MagicMock,
    RecordingStopEvent,
]:
    resolved_dispatcher = (
        dispatcher
        if dispatcher is not None
        else MagicMock()
    )

    resolved_backlog_provider = (
        backlog_provider
        if backlog_provider is not None
        else MagicMock(
            return_value=(
                OutboxBacklogSnapshot(
                    pending_count=0,
                    oldest_pending_at=None,
                )
            )
        )
    )

    resolved_metrics = (
        metrics
        if metrics is not None
        else MagicMock()
    )

    resolved_stop_event = (
        stop_event
        if stop_event is not None
        else RecordingStopEvent()
    )

    resolved_clock = (
        clock
        if clock is not None
        else FakeClock(
            0.0,
            0.1,
            0.1,
        )
    )

    runner = OutboxRunner(
        dispatcher=resolved_dispatcher,
        backlog_snapshot_provider=(
            resolved_backlog_provider
        ),
        metrics=resolved_metrics,
        poll_interval_seconds=1.0,
        error_backoff_seconds=5.0,
        metrics_interval_seconds=30.0,
        stop_event=resolved_stop_event,
        monotonic_clock=resolved_clock,
    )

    return (
        runner,
        resolved_dispatcher,
        resolved_backlog_provider,
        resolved_metrics,
        resolved_stop_event,
    )


def test_idle_iteration_waits_for_poll_interval() -> None:
    (
        runner,
        dispatcher,
        _,
        _,
        stop_event,
    ) = _runner()

    dispatcher.dispatch_once.return_value = (
        DispatchResult(
            claimed=0,
            published=0,
            failed=0,
        )
    )

    runner._run_iteration()

    assert stop_event.wait_calls == [
        1.0
    ]


def test_busy_iteration_does_not_wait() -> None:
    (
        runner,
        dispatcher,
        _,
        _,
        stop_event,
    ) = _runner()

    dispatcher.dispatch_once.return_value = (
        DispatchResult(
            claimed=2,
            published=2,
            failed=0,
        )
    )

    runner._run_iteration()

    assert stop_event.wait_calls == []


def test_dispatch_metrics_are_recorded_for_claimed_batch() -> None:
    (
        runner,
        dispatcher,
        _,
        metrics,
        _,
    ) = _runner(
        clock=FakeClock(
            10.0,
            10.25,
            10.25,
        )
    )

    result = DispatchResult(
        claimed=3,
        published=2,
        failed=1,
    )

    dispatcher.dispatch_once.return_value = (
        result
    )

    runner._run_iteration()

    metrics.record_dispatch.assert_called_once_with(
        result=result,
        duration_ms=250.0,
    )


def test_idle_iteration_does_not_record_dispatch_metrics() -> None:
    (
        runner,
        dispatcher,
        _,
        metrics,
        _,
    ) = _runner()

    dispatcher.dispatch_once.return_value = (
        DispatchResult(
            claimed=0,
            published=0,
            failed=0,
        )
    )

    runner._run_iteration()

    metrics.record_dispatch.assert_not_called()


def test_worker_failure_uses_error_backoff() -> None:
    (
        runner,
        dispatcher,
        _,
        metrics,
        stop_event,
    ) = _runner()

    dispatcher.dispatch_once.side_effect = (
        RuntimeError(
            "database unavailable"
        )
    )

    runner._run_iteration()

    metrics.record_worker_error.assert_called_once_with()

    assert stop_event.wait_calls == [
        5.0
    ]


def test_worker_failure_does_not_read_backlog() -> None:
    (
        runner,
        dispatcher,
        backlog_provider,
        _,
        _,
    ) = _runner()

    dispatcher.dispatch_once.side_effect = (
        RuntimeError(
            "database unavailable"
        )
    )

    runner._run_iteration()

    backlog_provider.assert_not_called()


def test_backlog_metric_is_recorded_when_due() -> None:
    backlog_provider = MagicMock(
        return_value=(
            OutboxBacklogSnapshot(
                pending_count=4,
                oldest_pending_at=None,
            )
        )
    )

    (
        runner,
        dispatcher,
        _,
        metrics,
        _,
    ) = _runner(
        backlog_provider=(
            backlog_provider
        ),
        clock=FakeClock(
            0.0,
            0.1,
            0.1,
        ),
    )

    dispatcher.dispatch_once.return_value = (
        DispatchResult(
            claimed=1,
            published=1,
            failed=0,
        )
    )

    runner._run_iteration()

    backlog_provider.assert_called_once_with()

    metrics.record_backlog.assert_called_once_with(
        snapshot=(
            backlog_provider.return_value
        ),
    )


def test_backlog_metric_respects_sampling_interval() -> None:
    (
        runner,
        dispatcher,
        backlog_provider,
        _,
        _,
    ) = _runner(
        clock=FakeClock(
            0.0,
            0.1,
            0.1,
            1.0,
            1.1,
            1.1,
        )
    )

    dispatcher.dispatch_once.return_value = (
        DispatchResult(
            claimed=1,
            published=1,
            failed=0,
        )
    )

    runner._run_iteration()
    runner._run_iteration()

    assert (
        backlog_provider.call_count
        == 1
    )


def test_metrics_failure_does_not_fail_dispatch_iteration() -> None:
    metrics = MagicMock()

    metrics.record_dispatch.side_effect = (
        RuntimeError(
            "cloudwatch unavailable"
        )
    )

    (
        runner,
        dispatcher,
        _,
        _,
        stop_event,
    ) = _runner(
        metrics=metrics
    )

    dispatcher.dispatch_once.return_value = (
        DispatchResult(
            claimed=1,
            published=1,
            failed=0,
        )
    )

    runner._run_iteration()

    assert stop_event.wait_calls == []


def test_backlog_provider_failure_does_not_fail_dispatch() -> None:
    backlog_provider = MagicMock(
        side_effect=RuntimeError(
            "backlog query unavailable"
        )
    )

    (
        runner,
        dispatcher,
        _,
        metrics,
        stop_event,
    ) = _runner(
        backlog_provider=(
            backlog_provider
        )
    )

    dispatcher.dispatch_once.return_value = (
        DispatchResult(
            claimed=1,
            published=1,
            failed=0,
        )
    )

    runner._run_iteration()

    metrics.record_dispatch.assert_called_once()

    assert stop_event.wait_calls == []


def test_run_forever_stops_without_claiming_new_batch() -> None:
    dispatcher = MagicMock()

    stop_event = (
        RecordingStopEvent()
    )

    stop_event.set()

    (
        runner,
        _,
        _,
        _,
        _,
    ) = _runner(
        dispatcher=dispatcher,
        stop_event=stop_event,
    )

    runner.run_forever()

    dispatcher.dispatch_once.assert_not_called()


def test_request_stop_sets_stop_event() -> None:
    stop_event = (
        RecordingStopEvent()
    )

    (
        runner,
        _,
        _,
        _,
        _,
    ) = _runner(
        stop_event=stop_event
    )

    assert not stop_event.is_set()

    runner.request_stop()

    assert stop_event.is_set()


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        (
            "poll_interval_seconds",
            0.0,
            (
                "poll_interval_seconds "
                "must be positive"
            ),
        ),
        (
            "error_backoff_seconds",
            0.0,
            (
                "error_backoff_seconds "
                "must be positive"
            ),
        ),
        (
            "metrics_interval_seconds",
            0.0,
            (
                "metrics_interval_seconds "
                "must be positive"
            ),
        ),
    ],
)
def test_runner_intervals_must_be_positive(
    field: str,
    value: float,
    message: str,
) -> None:
    kwargs: dict[str, object] = {
        "dispatcher": MagicMock(),
        "backlog_snapshot_provider": MagicMock(),
        "metrics": MagicMock(),
        "poll_interval_seconds": 1.0,
        "error_backoff_seconds": 5.0,
        "metrics_interval_seconds": 30.0,
    }

    kwargs[field] = value

    with pytest.raises(
        ValueError,
        match=message,
    ):
        OutboxRunner(
            **kwargs,
        )


def test_default_stop_event_supports_request_stop() -> None:
    runner = OutboxRunner(
        dispatcher=MagicMock(),
        backlog_snapshot_provider=MagicMock(),
        metrics=MagicMock(),
        poll_interval_seconds=1.0,
        error_backoff_seconds=5.0,
        metrics_interval_seconds=30.0,
    )

    assert isinstance(
        runner.stop_event,
        Event,
    )

    runner.request_stop()

    assert runner.stop_event.is_set()