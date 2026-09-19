from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete
from sqlalchemy.orm import Session

from libs.database import get_engine
from libs.database.models.outbox import OutboxEventModel
from libs.database.repositories.outbox import (
    OutboxRepository,
)
from libs.events.envelope import EventEnvelope

pytestmark = pytest.mark.integration


@pytest.fixture
def db_session() -> Session:
    """
    Run repository integration tests inside an outer transaction.

    The database schema must already be managed by Alembic.
    Tests intentionally do not call Base.metadata.create_all().

    The outer transaction is rolled back after each test so
    repository changes do not persist.
    """

    engine = get_engine()

    connection = engine.connect()
    transaction = connection.begin()

    session = Session(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )

    try:
        yield session

    finally:
        session.close()

        if transaction.is_active:
            transaction.rollback()

        connection.close()


def _event(
    *,
    occurred_at: datetime | None = None,
) -> EventEnvelope[dict[str, object]]:
    """
    Build one canonical test integration event.
    """

    event_id = uuid4()

    return EventEnvelope[
        dict[str, object]
    ](
        event_id=event_id,
        event_type="test.outbox.created",
        schema_version=1,
        occurred_at=(
            occurred_at
            if occurred_at is not None
            else datetime.now(UTC)
        ),
        source="outbox-repository-test",
        payload={
            "event_id": str(event_id),
        },
    )


def _persist_event(
    session: Session,
    *,
    occurred_at: datetime | None = None,
) -> OutboxEventModel:
    """
    Persist one test event without committing the transaction.
    """

    repository = OutboxRepository(
        session
    )

    event = _event(
        occurred_at=occurred_at,
    )

    return repository.add_event(
        aggregate_type="test",
        aggregate_id=str(
            event.event_id
        ),
        event=event,
    )


def _find_by_event_id(
    events: list[OutboxEventModel],
    event_id: UUID,
) -> OutboxEventModel | None:
    """
    Return a claimed event with the requested event_id.
    """

    return next(
        (
            event
            for event in events
            if event.event_id == event_id
        ),
        None,
    )


def test_claim_pending_claims_due_event(
    db_session: Session,
) -> None:
    now = datetime.now(UTC)

    model = _persist_event(
        db_session,
        occurred_at=(
            now
            - timedelta(
                seconds=10
            )
        ),
    )

    repository = OutboxRepository(
        db_session
    )

    claimed = repository.claim_pending(
        worker_id="worker-001",
        batch_size=1000,
        lease_seconds=30,
        now=now,
    )

    claimed_event = _find_by_event_id(
        claimed,
        model.event_id,
    )

    assert claimed_event is not None

    assert (
        claimed_event.locked_by
        == "worker-001"
    )

    assert (
        claimed_event.locked_until
        == now
        + timedelta(
            seconds=30
        )
    )

    assert claimed_event.published_at is None


def test_active_lease_prevents_reclaim(
    db_session: Session,
) -> None:
    now = datetime.now(UTC)

    model = _persist_event(
        db_session,
        occurred_at=(
            now
            - timedelta(
                seconds=10
            )
        ),
    )

    repository = OutboxRepository(
        db_session
    )

    first_claim = repository.claim_pending(
        worker_id="worker-001",
        batch_size=1000,
        lease_seconds=60,
        now=now,
    )

    assert (
        _find_by_event_id(
            first_claim,
            model.event_id,
        )
        is not None
    )

    second_claim = repository.claim_pending(
        worker_id="worker-002",
        batch_size=1000,
        lease_seconds=60,
        now=(
            now
            + timedelta(
                seconds=10
            )
        ),
    )

    assert (
        _find_by_event_id(
            second_claim,
            model.event_id,
        )
        is None
    )


def test_expired_lease_can_be_reclaimed(
    db_session: Session,
) -> None:
    now = datetime.now(UTC)

    model = _persist_event(
        db_session,
        occurred_at=(
            now
            - timedelta(
                minutes=1
            )
        ),
    )

    model.locked_by = "dead-worker"

    model.locked_until = (
        now
        - timedelta(
            seconds=1
        )
    )

    db_session.flush()

    repository = OutboxRepository(
        db_session
    )

    claimed = repository.claim_pending(
        worker_id="worker-recovery",
        batch_size=1000,
        lease_seconds=30,
        now=now,
    )

    claimed_event = _find_by_event_id(
        claimed,
        model.event_id,
    )

    assert claimed_event is not None

    assert (
        claimed_event.locked_by
        == "worker-recovery"
    )

    assert (
        claimed_event.locked_until
        == now
        + timedelta(
            seconds=30
        )
    )


def test_published_event_cannot_be_claimed(
    db_session: Session,
) -> None:
    now = datetime.now(UTC)

    model = _persist_event(
        db_session,
        occurred_at=(
            now
            - timedelta(
                minutes=1
            )
        ),
    )

    model.published_at = (
        now
        - timedelta(
            seconds=10
        )
    )

    db_session.flush()

    repository = OutboxRepository(
        db_session
    )

    claimed = repository.claim_pending(
        worker_id="worker-001",
        batch_size=1000,
        lease_seconds=30,
        now=now,
    )

    assert (
        _find_by_event_id(
            claimed,
            model.event_id,
        )
        is None
    )


def test_mark_published_releases_lease(
    db_session: Session,
) -> None:
    now = datetime.now(UTC)

    model = _persist_event(
        db_session,
        occurred_at=(
            now
            - timedelta(
                seconds=10
            )
        ),
    )

    repository = OutboxRepository(
        db_session
    )

    repository.claim_pending(
        worker_id="worker-001",
        batch_size=1000,
        lease_seconds=30,
        now=now,
    )

    published_at = (
        now
        + timedelta(
            seconds=5
        )
    )

    updated = repository.mark_published(
        event_id=model.event_id,
        worker_id="worker-001",
        published_at=published_at,
    )

    assert updated is True

    db_session.refresh(
        model
    )

    assert (
        model.published_at
        == published_at
    )

    assert model.locked_by is None
    assert model.locked_until is None
    assert model.last_error is None


def test_mark_failed_schedules_retry_and_releases_lease(
    db_session: Session,
) -> None:
    now = datetime.now(UTC)

    model = _persist_event(
        db_session,
        occurred_at=(
            now
            - timedelta(
                seconds=10
            )
        ),
    )

    repository = OutboxRepository(
        db_session
    )

    repository.claim_pending(
        worker_id="worker-001",
        batch_size=1000,
        lease_seconds=30,
        now=now,
    )

    retry_at = (
        now
        + timedelta(
            seconds=30
        )
    )

    updated = repository.mark_failed(
        event_id=model.event_id,
        worker_id="worker-001",
        error="eventbridge unavailable",
        next_attempt_at=retry_at,
    )

    assert updated is True

    db_session.refresh(
        model
    )

    assert model.published_at is None

    assert model.attempt_count == 1

    assert (
        model.last_error
        == "eventbridge unavailable"
    )

    assert (
        model.next_attempt_at
        == retry_at
    )

    assert model.locked_by is None
    assert model.locked_until is None


def test_skip_locked_prevents_concurrent_duplicate_claim() -> None:
    """
    Verify PostgreSQL SKIP LOCKED behavior with two independent
    database transactions.

    Worker A claims and holds the row lock.

    Worker B must skip that locked row instead of blocking or
    claiming the same event.
    """

    engine = get_engine()

    now = datetime.now(UTC)

    event = _event(
        occurred_at=(
            now
            - timedelta(
                seconds=10
            )
        ),
    )

    event_id = event.event_id

    setup_session = Session(
        bind=engine,
        expire_on_commit=False,
    )

    worker_a_session = Session(
        bind=engine,
        expire_on_commit=False,
    )

    worker_b_session = Session(
        bind=engine,
        expire_on_commit=False,
    )

    cleanup_session = Session(
        bind=engine,
        expire_on_commit=False,
    )

    try:
        setup_repository = (
            OutboxRepository(
                setup_session
            )
        )

        setup_repository.add_event(
            aggregate_type="test",
            aggregate_id=str(
                event_id
            ),
            event=event,
        )

        setup_session.commit()

        worker_a_repository = (
            OutboxRepository(
                worker_a_session
            )
        )

        worker_b_repository = (
            OutboxRepository(
                worker_b_session
            )
        )

        worker_a_claim = (
            worker_a_repository
            .claim_pending(
                worker_id="worker-a",
                batch_size=1000,
                lease_seconds=30,
                now=now,
            )
        )

        assert (
            _find_by_event_id(
                worker_a_claim,
                event_id,
            )
            is not None
        )

        # Worker A intentionally does not commit yet.
        # The SELECT FOR UPDATE row lock remains active.

        worker_b_claim = (
            worker_b_repository
            .claim_pending(
                worker_id="worker-b",
                batch_size=1000,
                lease_seconds=30,
                now=now,
            )
        )

        assert (
            _find_by_event_id(
                worker_b_claim,
                event_id,
            )
            is None
        )

    finally:
        worker_b_session.rollback()
        worker_a_session.rollback()

        worker_b_session.close()
        worker_a_session.close()

        setup_session.close()

        cleanup_session.execute(
            delete(
                OutboxEventModel
            ).where(
                OutboxEventModel.event_id
                == event_id
            )
        )

        cleanup_session.commit()
        cleanup_session.close()