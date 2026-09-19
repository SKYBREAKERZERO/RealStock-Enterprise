from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from libs.database.repositories.outbox import (
    ClaimedOutboxEvent,
    OutboxRepository,
)
from services.outbox_dispatcher.publisher import (
    EventBridgeOutboxPublisher,
)

DEFAULT_BATCH_SIZE = 10
DEFAULT_LEASE_SECONDS = 60

RETRY_DELAYS_SECONDS = (
    5,
    30,
    120,
    600,
)


@dataclass(
    frozen=True,
    slots=True,
)
class DispatchResult:
    """
    Summary of one dispatcher iteration.

    claimed:
        Number of outbox events claimed in the database.

    published:
        Number of events successfully published and acknowledged.

    failed:
        Number of publication attempts that failed and were
        scheduled for retry.
    """

    claimed: int
    published: int
    failed: int


class OutboxDispatcher:
    """
    Reliable transactional outbox dispatcher.

    Processing flow:

        TX #1
        claim_pending()
        commit
            ↓
        EventBridge network I/O
            ↓
        TX #2
        mark_published() or mark_failed()
        commit

    No EventBridge network request is performed while the claim
    transaction is open.

    Delivery semantics are at-least-once.
    """

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        publisher: EventBridgeOutboxPublisher,
        worker_id: str,
        batch_size: int = DEFAULT_BATCH_SIZE,
        lease_seconds: int = DEFAULT_LEASE_SECONDS,
    ) -> None:
        normalized_worker_id = (
            worker_id.strip()
        )

        if not normalized_worker_id:
            raise ValueError(
                "worker_id must not be empty"
            )

        if batch_size < 1:
            raise ValueError(
                "batch_size must be greater than zero"
            )

        if lease_seconds < 1:
            raise ValueError(
                "lease_seconds must be greater than zero"
            )

        self._session_factory = (
            session_factory
        )

        self._publisher = publisher

        self._worker_id = (
            normalized_worker_id
        )

        self._batch_size = (
            batch_size
        )

        self._lease_seconds = (
            lease_seconds
        )

    @property
    def worker_id(
        self,
    ) -> str:
        return self._worker_id

    @property
    def batch_size(
        self,
    ) -> int:
        return self._batch_size

    @property
    def lease_seconds(
        self,
    ) -> int:
        return self._lease_seconds

    def dispatch_once(
        self,
        *,
        now: datetime | None = None,
    ) -> DispatchResult:
        """
        Claim and process one batch of dispatchable outbox events.

        The claim transaction is committed before publication
        begins.

        Each success or failure acknowledgement uses a separate
        database transaction.
        """

        effective_now = (
            self._resolve_utc(
                now
            )
        )

        events = self._claim_events(
            now=effective_now
        )

        published = 0
        failed = 0

        for event in events:
            try:
                self._publisher.publish(
                    event
                )

            except Exception as exc:
                self._record_failure(
                    event=event,
                    error=str(exc),
                    now=effective_now,
                )

                failed += 1

            else:
                self._record_success(
                    event=event,
                    published_at=effective_now,
                )

                published += 1

        return DispatchResult(
            claimed=len(events),
            published=published,
            failed=failed,
        )

    # ==========================================================
    # Claim transaction
    # ==========================================================

    def _claim_events(
        self,
        *,
        now: datetime,
    ) -> list[ClaimedOutboxEvent]:
        """
        Claim one batch and commit the worker leases.

        This transaction must finish before EventBridge is called.
        """

        with self._session_factory() as session:
            repository = OutboxRepository(
                session
            )

            try:
                events = (
                    repository.claim_pending(
                        worker_id=(
                            self._worker_id
                        ),
                        batch_size=(
                            self._batch_size
                        ),
                        lease_seconds=(
                            self._lease_seconds
                        ),
                        now=now,
                    )
                )

                session.commit()

            except Exception:
                session.rollback()
                raise

        return events

    # ==========================================================
    # Success transaction
    # ==========================================================

    def _record_success(
        self,
        *,
        event: ClaimedOutboxEvent,
        published_at: datetime,
    ) -> None:
        """
        Acknowledge one successfully published event.
        """

        with self._session_factory() as session:
            repository = OutboxRepository(
                session
            )

            try:
                updated = (
                    repository.mark_published(
                        event_id=event.event_id,
                        worker_id=(
                            self._worker_id
                        ),
                        published_at=(
                            published_at
                        ),
                    )
                )

                if not updated:
                    raise RuntimeError(
                        "outbox event publication "
                        "acknowledgement rejected"
                    )

                session.commit()

            except Exception:
                session.rollback()
                raise

    # ==========================================================
    # Failure transaction
    # ==========================================================

    def _record_failure(
        self,
        *,
        event: ClaimedOutboxEvent,
        error: str,
        now: datetime,
    ) -> None:
        """
        Record one publication failure and schedule retry.
        """

        retry_delay = (
            self._retry_delay(
                attempt_count=(
                    event.attempt_count
                )
            )
        )

        next_attempt_at = (
            now
            + retry_delay
        )

        with self._session_factory() as session:
            repository = OutboxRepository(
                session
            )

            try:
                updated = (
                    repository.mark_failed(
                        event_id=event.event_id,
                        worker_id=(
                            self._worker_id
                        ),
                        error=error,
                        next_attempt_at=(
                            next_attempt_at
                        ),
                    )
                )

                if not updated:
                    raise RuntimeError(
                        "outbox event failure "
                        "acknowledgement rejected"
                    )

                session.commit()

            except Exception:
                session.rollback()
                raise

    # ==========================================================
    # Retry policy
    # ==========================================================

    @staticmethod
    def _retry_delay(
        *,
        attempt_count: int,
    ) -> timedelta:
        """
        Calculate retry delay from the number of previous failures.

        attempt_count=0  ->   5 seconds
        attempt_count=1  ->  30 seconds
        attempt_count=2  -> 120 seconds
        attempt_count>=3 -> 600 seconds
        """

        if attempt_count < 0:
            raise ValueError(
                "attempt_count must not be negative"
            )

        index = min(
            attempt_count,
            len(
                RETRY_DELAYS_SECONDS
            )
            - 1,
        )

        return timedelta(
            seconds=(
                RETRY_DELAYS_SECONDS[
                    index
                ]
            )
        )

    # ==========================================================
    # Time normalization
    # ==========================================================

    @staticmethod
    def _resolve_utc(
        value: datetime | None,
    ) -> datetime:
        """
        Resolve one unambiguous UTC timestamp.
        """

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