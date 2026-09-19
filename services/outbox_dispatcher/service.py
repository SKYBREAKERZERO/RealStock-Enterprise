from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Protocol

from sqlalchemy.orm import Session, sessionmaker

from libs.database.repositories.outbox import (
    ClaimedOutboxEvent,
    OutboxRepository,
)


class OutboxPublisher(Protocol):
    def publish(
        self,
        event: ClaimedOutboxEvent,
    ) -> object: ...


@dataclass(frozen=True, slots=True)
class DispatchResult:
    claimed: int
    published: int
    failed: int


def utc_now() -> datetime:
    return datetime.now(UTC)


_RETRY_DELAYS = (
    timedelta(seconds=5),
    timedelta(seconds=30),
    timedelta(minutes=2),
    timedelta(minutes=10),
)


def retry_delay_for(
    attempt_count: int,
) -> timedelta:
    if attempt_count < 0:
        raise ValueError(
            "attempt_count must not be negative"
        )

    index = min(
        attempt_count,
        len(_RETRY_DELAYS) - 1,
    )

    return _RETRY_DELAYS[index]


class OutboxDispatcher:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        publisher: OutboxPublisher,
        worker_id: str,
        batch_size: int = 10,
        lease_duration: timedelta = timedelta(
            seconds=30
        ),
        clock: Callable[[], datetime] = utc_now,
    ) -> None:
        normalized_worker_id = worker_id.strip()

        if not normalized_worker_id:
            raise ValueError(
                "worker_id must not be empty"
            )

        if batch_size < 1:
            raise ValueError(
                "batch_size must be greater than zero"
            )

        if lease_duration <= timedelta(0):
            raise ValueError(
                "lease_duration must be positive"
            )

        self._session_factory = session_factory
        self._publisher = publisher
        self._worker_id = normalized_worker_id
        self._batch_size = batch_size
        self._lease_duration = lease_duration
        self._clock = clock

    def dispatch_once(
        self,
    ) -> DispatchResult:
        events = self._claim_batch()

        published = 0
        failed = 0

        for event in events:
            try:
                self._publisher.publish(
                    event
                )
            except Exception as exc:
                self._record_failure(
                    event,
                    exc,
                )
                failed += 1
            else:
                self._record_success(
                    event
                )
                published += 1

        return DispatchResult(
            claimed=len(events),
            published=published,
            failed=failed,
        )

    def _claim_batch(
        self,
    ) -> list[ClaimedOutboxEvent]:
        now = self._clock()

        with self._session_factory() as session:
            repository = OutboxRepository(
                session
            )

            events = repository.claim_pending(
                worker_id=self._worker_id,
                now=now,
                lease_duration=self._lease_duration,
                batch_size=self._batch_size,
            )

            session.commit()

            return events

    def _record_success(
        self,
        event: ClaimedOutboxEvent,
    ) -> None:
        with self._session_factory() as session:
            repository = OutboxRepository(
                session
            )

            repository.mark_published(
                event_id=event.event_id,
                worker_id=self._worker_id,
                published_at=self._clock(),
            )

            session.commit()

    def _record_failure(
        self,
        event: ClaimedOutboxEvent,
        exc: Exception,
    ) -> None:
        now = self._clock()

        next_attempt_at = (
            now
            + retry_delay_for(
                event.attempt_count
            )
        )

        error = (
            f"{type(exc).__name__}: {exc}"
        )

        with self._session_factory() as session:
            repository = OutboxRepository(
                session
            )

            repository.mark_failed(
                event_id=event.event_id,
                worker_id=self._worker_id,
                error=error,
                next_attempt_at=next_attempt_at,
            )

            session.commit()