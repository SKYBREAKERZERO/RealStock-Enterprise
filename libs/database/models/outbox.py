from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    DateTime,
    Index,
    Integer,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from libs.database.models.base import Base


def utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(UTC)


class OutboxEventModel(Base):
    """
    Persistent transactional outbox event.

    Business state and its corresponding integration event are
    persisted in the same PostgreSQL transaction.

    Delivery semantics are at-least-once. event_id remains stable
    across retries so consumers can implement idempotency.

    Dispatcher workers coordinate using PostgreSQL row locking and
    a time-bounded lease.
    """

    __tablename__ = "outbox_events"

    __table_args__ = (
        Index(
            "ix_outbox_events_pending",
            "published_at",
            "occurred_at",
        ),
        Index(
            "ix_outbox_events_dispatchable",
            "published_at",
            "next_attempt_at",
            "occurred_at",
        ),
        Index(
            "ix_outbox_events_aggregate",
            "aggregate_type",
            "aggregate_id",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    event_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
        unique=True,
    )

    aggregate_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    aggregate_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    event_type: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    schema_version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    source: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
    )

    correlation_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        nullable=False,
    )

    causation_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )

    trace_context: Mapped[
        dict[str, str] | None
    ] = mapped_column(
        JSONB,
        nullable=True,
    )

    payload: Mapped[
        dict[str, object]
    ] = mapped_column(
        JSONB,
        nullable=False,
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
    )

    published_at: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        server_default=func.now(),
    )

    last_error: Mapped[
        str | None
    ] = mapped_column(
        Text,
        nullable=True,
    )

    locked_until: Mapped[
        datetime | None
    ] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    locked_by: Mapped[
        str | None
    ] = mapped_column(
        String(128),
        nullable=True,
    )