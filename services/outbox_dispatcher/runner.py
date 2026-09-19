from __future__ import annotations

import logging
from collections.abc import Callable
from threading import Event
from time import monotonic
from typing import Protocol

from libs.database.repositories.outbox import (
    OutboxBacklogSnapshot,
)
from services.outbox_dispatcher.dispatcher import (
    DispatchResult,
)
from services.outbox_dispatcher.metrics import (
    OutboxMetrics,
)

logger = logging.getLogger(__name__)


class Dispatcher(Protocol):
    def dispatch_once(
        self,
    ) -> DispatchResult: ...


class StopEvent(Protocol):
    def is_set(
        self,
    ) -> bool: ...

    def wait(
        self,
        timeout: float | None = None,
    ) -> bool: ...


BacklogSnapshotProvider = Callable[
    [],
    OutboxBacklogSnapshot,
]

MonotonicClock = Callable[
    [],
    float,
]


class OutboxRunner:
    """
    Long-running runtime loop for the transactional outbox worker.

    Responsibilities:
    - repeatedly invoke the dispatcher;
    - avoid busy-looping when the outbox is empty;
    - back off after worker-level failures;
    - publish best-effort operational metrics;
    - stop gracefully when requested.

    Non-responsibilities:
    - claim semantics;
    - lease ownership;
    - EventBridge publication;
    - retry scheduling;
    - database transaction ownership.

    SIGTERM/SIGINT handling belongs to the composition root. The
    signal handler should only set stop_event. This runner will
    finish the current dispatch iteration and then exit.
    """

    def __init__(
        self,
        *,
        dispatcher: Dispatcher,
        backlog_snapshot_provider: (
            BacklogSnapshotProvider
        ),
        metrics: OutboxMetrics,
        poll_interval_seconds: float,
        error_backoff_seconds: float,
        metrics_interval_seconds: float,
        stop_event: StopEvent | None = None,
        monotonic_clock: MonotonicClock = monotonic,
    ) -> None:
        if poll_interval_seconds <= 0:
            raise ValueError(
                "poll_interval_seconds must be positive"
            )

        if error_backoff_seconds <= 0:
            raise ValueError(
                "error_backoff_seconds must be positive"
            )

        if metrics_interval_seconds <= 0:
            raise ValueError(
                "metrics_interval_seconds must be positive"
            )

        self._dispatcher = dispatcher

        self._backlog_snapshot_provider = (
            backlog_snapshot_provider
        )

        self._metrics = metrics

        self._poll_interval_seconds = (
            poll_interval_seconds
        )

        self._error_backoff_seconds = (
            error_backoff_seconds
        )

        self._metrics_interval_seconds = (
            metrics_interval_seconds
        )

        self._stop_event = (
            stop_event
            if stop_event is not None
            else Event()
        )

        self._monotonic_clock = (
            monotonic_clock
        )

        self._next_backlog_metric_at = 0.0

    @property
    def stop_event(
        self,
    ) -> StopEvent:
        return self._stop_event

    def request_stop(
        self,
    ) -> None:
        """
        Request graceful shutdown when the underlying event supports it.
        """

        setter = getattr(
            self._stop_event,
            "set",
            None,
        )

        if setter is None:
            raise RuntimeError(
                "configured stop_event does not support set()"
            )

        setter()

    def run_forever(
        self,
    ) -> None:
        """
        Run until stop is requested.

        A stop request never interrupts an in-progress dispatch_once().
        The current iteration completes first, then no new batch is
        claimed.
        """

        logger.info(
            "outbox dispatcher worker started"
        )

        try:
            while not self._stop_event.is_set():
                self._run_iteration()

        finally:
            logger.info(
                "outbox dispatcher worker stopped"
            )

    def _run_iteration(
        self,
    ) -> None:
        started_at = (
            self._monotonic_clock()
        )

        try:
            result = (
                self._dispatcher
                .dispatch_once()
            )

        except Exception:
            logger.exception(
                "outbox dispatcher iteration failed"
            )

            self._record_worker_error_safely()

            self._wait(
                self._error_backoff_seconds
            )

            return

        finished_at = (
            self._monotonic_clock()
        )

        duration_ms = max(
            (
                finished_at
                - started_at
            )
            * 1000.0,
            0.0,
        )

        if result.claimed > 0:
            self._record_dispatch_safely(
                result=result,
                duration_ms=duration_ms,
            )

        self._record_backlog_if_due()

        if result.claimed == 0:
            self._wait(
                self._poll_interval_seconds
            )

    def _record_backlog_if_due(
        self,
    ) -> None:
        now = (
            self._monotonic_clock()
        )

        if (
            now
            < self._next_backlog_metric_at
        ):
            return

        self._next_backlog_metric_at = (
            now
            + self._metrics_interval_seconds
        )

        try:
            snapshot = (
                self._backlog_snapshot_provider()
            )

        except Exception:
            logger.exception(
                "failed to read outbox backlog snapshot"
            )
            return

        try:
            self._metrics.record_backlog(
                snapshot=snapshot,
            )

        except Exception:
            logger.exception(
                "failed to publish outbox backlog metrics"
            )

    def _record_dispatch_safely(
        self,
        *,
        result: DispatchResult,
        duration_ms: float,
    ) -> None:
        try:
            self._metrics.record_dispatch(
                result=result,
                duration_ms=duration_ms,
            )

        except Exception:
            logger.exception(
                "failed to publish outbox dispatch metrics"
            )

    def _record_worker_error_safely(
        self,
    ) -> None:
        try:
            self._metrics.record_worker_error()

        except Exception:
            logger.exception(
                "failed to publish outbox worker error metric"
            )

    def _wait(
        self,
        seconds: float,
    ) -> None:
        """
        Wait interruptibly.

        Event.wait() allows SIGTERM handling to wake the worker
        immediately instead of waiting for time.sleep() to expire.
        """

        self._stop_event.wait(
            timeout=seconds
        )