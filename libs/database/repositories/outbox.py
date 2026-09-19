from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

import libs.database.models.outbox as outbox_models
from libs.events.envelope import EventEnvelope


@dataclass(
    frozen=True,
    slots=True,
)
class ClaimedOutboxEvent:
    """
    Immutable snapshot of a claimed transactional outbox event.

    The dispatcher receives this DTO after the claim transaction
    has completed.

    It deliberately avoids exposing a live SQLAlchemy ORM instance
    to transport code such as the EventBridge publisher.

    The stable business event_id is preserved across retries.
    """

    id: UUID
    event_id: UUID

    aggregate_type: str
    aggregate_id: str

    event_type: str
    schema_version: int
    source: str

    correlation_id: UUID
    causation_id: UUID | None

    trace_context: dict[str, str] | None
    payload: dict[str, object]

    occurred_at: datetime

    attempt_count: int

    published_at: datetime | None = None
    locked_by: str | None = None
    locked_until: datetime | None = None


@dataclass(
    frozen=True,
    slots=True,
)
class OutboxBacklogSnapshot:
    """
    Immutable operational snapshot of the transactional outbox backlog.

    pending_count:
        Number of unpublished outbox events.

    oldest_pending_at:
        Database creation time of the oldest unpublished event.

        None means there are currently no unpublished events.

    The snapshot intentionally includes:
    - immediately dispatchable events;
    - events waiting for retry;
    - events protected by an active worker lease.

    Any event with published_at set is excluded.
    """

    pending_count: int
    oldest_pending_at: datetime | None


class OutboxRepository:
    """
    Repository for transactional outbox persistence and dispatch state.

    Transaction ownership belongs to the caller.

    This repository may:
    - add rows;
    - query rows;
    - update rows;
    - flush changes.

    This repository must not:
    - commit;
    - rollback.

    Dispatcher claims use PostgreSQL FOR UPDATE SKIP LOCKED together
    with a time-bounded lease.

    claim_pending() returns immutable ClaimedOutboxEvent snapshots
    rather than live ORM entities.

    get_backlog_snapshot() provides a read-only operational view of
    unpublished events for observability.

    Delivery semantics are at-least-once.
    """

    def __init__(
        self,
        session: Session,
    ) -> None:
        self._session = session

    # ==========================================================
    # Event persistence
    # ==========================================================

    def add_event(
        self,
        *,
        aggregate_type: str,
        aggregate_id: str,
        event: EventEnvelope[dict[str, object]],
    ) -> outbox_models.OutboxEventModel:
        """
        Persist an event in the caller's current transaction.

        Newly-created outbox events are immediately eligible for
        dispatch, so next_attempt_at initially equals occurred_at.

        The repository flushes but never commits.
        """

        normalized_aggregate_type = (
            aggregate_type.strip()
        )

        normalized_aggregate_id = (
            aggregate_id.strip()
        )

        if not normalized_aggregate_type:
            raise ValueError(
                "aggregate_type must not be empty"
            )

        if not normalized_aggregate_id:
            raise ValueError(
                "aggregate_id must not be empty"
            )

        model = (
            outbox_models.OutboxEventModel(
                event_id=event.event_id,
                aggregate_type=(
                    normalized_aggregate_type
                ),
                aggregate_id=(
                    normalized_aggregate_id
                ),
                event_type=event.event_type,
                schema_version=event.schema_version,
                source=event.source,
                correlation_id=event.correlation_id,
                causation_id=event.causation_id,
                trace_context=event.trace_context,
                payload=event.payload,
                occurred_at=event.occurred_at,
                next_attempt_at=event.occurred_at,
            )
        )

        self._session.add(
            model
        )

        self._session.flush()

        return model

    # ==========================================================
    # Operational backlog snapshot
    # ==========================================================

    def get_backlog_snapshot(
        self,
    ) -> OutboxBacklogSnapshot:
        """
        Return the current unpublished outbox backlog.

        All unpublished events are considered pending, including:
        - events currently eligible for dispatch;
        - events waiting for retry;
        - events currently protected by an active worker lease.

        Published events are excluded.

        created_at is used for oldest_pending_at because this metric
        describes how long an event has remained in the outbox table,
        rather than when the underlying business event occurred.

        This query is read-only and does not:
        - flush;
        - commit;
        - rollback;
        - acquire row locks.
        """

        statement = (
            select(
                func.count(
                    outbox_models
                    .OutboxEventModel
                    .id
                ),
                func.min(
                    outbox_models
                    .OutboxEventModel
                    .created_at
                ),
            )
            .where(
                outbox_models
                .OutboxEventModel
                .published_at
                .is_(None)
            )
        )

        pending_count, oldest_pending_at = (
            self._session
            .execute(statement)
            .one()
        )

        return OutboxBacklogSnapshot(
            pending_count=int(
                pending_count
            ),
            oldest_pending_at=(
                oldest_pending_at
            ),
        )

    # ==========================================================
    # Dispatcher claim
    # ==========================================================

    def claim_pending(
        self,
        *,
        worker_id: str,
        batch_size: int,
        lease_seconds: int,
        now: datetime | None = None,
    ) -> list[ClaimedOutboxEvent]:
        """
        Claim dispatchable events for one dispatcher worker.

        An event is dispatchable when:
        - published_at is NULL;
        - next_attempt_at is due;
        - there is no active lease.

        PostgreSQL FOR UPDATE SKIP LOCKED prevents concurrent
        dispatcher workers from claiming the same row.

        The lease is flushed but not committed here.

        The caller must commit the claim transaction before making
        external network calls.

        Returned values are immutable DTO snapshots rather than
        SQLAlchemy ORM entities.
        """

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

        claimed_at = (
            self._resolve_utc(
                now
            )
        )

        lease_until = (
            claimed_at
            + timedelta(
                seconds=lease_seconds
            )
        )

        statement = (
            select(
                outbox_models.OutboxEventModel
            )
            .where(
                outbox_models
                .OutboxEventModel
                .published_at
                .is_(None),
                outbox_models
                .OutboxEventModel
                .next_attempt_at
                <= claimed_at,
                or_(
                    outbox_models
                    .OutboxEventModel
                    .locked_until
                    .is_(None),
                    outbox_models
                    .OutboxEventModel
                    .locked_until
                    <= claimed_at,
                ),
            )
            .order_by(
                outbox_models
                .OutboxEventModel
                .occurred_at
                .asc(),
                outbox_models
                .OutboxEventModel
                .id
                .asc(),
            )
            .limit(
                batch_size
            )
            .with_for_update(
                skip_locked=True
            )
        )

        models = list(
            self._session
            .execute(statement)
            .scalars()
            .all()
        )

        for model in models:
            model.locked_by = (
                normalized_worker_id
            )

            model.locked_until = (
                lease_until
            )

        self._session.flush()

        return [
            self._to_claimed_event(
                model
            )
            for model in models
        ]

    # ==========================================================
    # Successful publication
    # ==========================================================

    def mark_published(
        self,
        *,
        event_id: UUID,
        worker_id: str,
        published_at: datetime | None = None,
    ) -> bool:
        """
        Mark a worker-owned event as successfully published.

        Only the worker currently owning the lease may acknowledge
        the event.
        """

        normalized_worker_id = (
            worker_id.strip()
        )

        if not normalized_worker_id:
            raise ValueError(
                "worker_id must not be empty"
            )

        model = (
            self._get_claimed_model(
                event_id=event_id,
                worker_id=(
                    normalized_worker_id
                ),
            )
        )

        if model is None:
            return False

        model.published_at = (
            self._resolve_utc(
                published_at
            )
        )

        model.locked_by = None
        model.locked_until = None
        model.last_error = None

        self._session.flush()

        return True

    # ==========================================================
    # Failed publication
    # ==========================================================

    def mark_failed(
        self,
        *,
        event_id: UUID,
        worker_id: str,
        error: str,
        next_attempt_at: datetime,
    ) -> bool:
        """
        Record a failed publication and schedule another attempt.

        Failure handling:
        - increment attempt_count;
        - record last_error;
        - update next_attempt_at;
        - release the worker lease;
        - leave published_at NULL.
        """

        normalized_worker_id = (
            worker_id.strip()
        )

        if not normalized_worker_id:
            raise ValueError(
                "worker_id must not be empty"
            )

        model = (
            self._get_claimed_model(
                event_id=event_id,
                worker_id=(
                    normalized_worker_id
                ),
            )
        )

        if model is None:
            return False

        normalized_error = (
            error.strip()
        )

        model.attempt_count += 1

        model.last_error = (
            normalized_error
            if normalized_error
            else "unknown publish failure"
        )

        model.next_attempt_at = (
            self._resolve_utc(
                next_attempt_at
            )
        )

        model.locked_by = None
        model.locked_until = None

        self._session.flush()

        return True

    # ==========================================================
    # Internal ORM query
    # ==========================================================

    def _get_claimed_model(
        self,
        *,
        event_id: UUID,
        worker_id: str,
    ) -> (
        outbox_models.OutboxEventModel
        | None
    ):
        """
        Load one unpublished ORM row currently owned by worker_id.
        """

        statement = (
            select(
                outbox_models.OutboxEventModel
            )
            .where(
                outbox_models
                .OutboxEventModel
                .event_id
                == event_id,
                outbox_models
                .OutboxEventModel
                .locked_by
                == worker_id,
                outbox_models
                .OutboxEventModel
                .published_at
                .is_(None),
            )
        )

        return (
            self._session
            .execute(statement)
            .scalar_one_or_none()
        )

    # ==========================================================
    # ORM -> immutable DTO
    # ==========================================================

    @staticmethod
    def _to_claimed_event(
        model: outbox_models.OutboxEventModel,
    ) -> ClaimedOutboxEvent:
        """
        Convert a live ORM entity into a dispatcher-safe snapshot.
        """

        trace_context = (
            dict(model.trace_context)
            if model.trace_context is not None
            else None
        )

        payload = dict(
            model.payload
        )

        return ClaimedOutboxEvent(
            id=model.id,
            event_id=model.event_id,
            aggregate_type=model.aggregate_type,
            aggregate_id=model.aggregate_id,
            event_type=model.event_type,
            schema_version=model.schema_version,
            source=model.source,
            correlation_id=model.correlation_id,
            causation_id=model.causation_id,
            trace_context=trace_context,
            payload=payload,
            occurred_at=model.occurred_at,
            attempt_count=model.attempt_count,
            published_at=model.published_at,
            locked_by=model.locked_by,
            locked_until=model.locked_until,
        )

    # ==========================================================
    # Time normalization
    # ==========================================================

    @staticmethod
    def _resolve_utc(
        value: datetime | None,
    ) -> datetime:
        """
        Return an unambiguous timezone-aware UTC timestamp.
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