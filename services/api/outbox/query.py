from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from libs.database.models.outbox import OutboxEventModel
from services.api.outbox.status import OutboxEventStatus


@dataclass(frozen=True, slots=True)
class OutboxEventRecord:
    event_id: UUID
    aggregate_type: str
    aggregate_id: str
    event_type: str
    schema_version: int
    source: str
    occurred_at: datetime
    created_at: datetime
    published_at: datetime | None
    attempt_count: int
    next_attempt_at: datetime
    last_error: str | None
    locked_by: str | None
    locked_until: datetime | None
    status: OutboxEventStatus


@dataclass(frozen=True, slots=True)
class OutboxSummaryRecord:
    total_count: int
    pending_count: int
    published_count: int
    failed_count: int
    unpublished_count: int
    oldest_unpublished_at: datetime | None


class OutboxQueryService:
    """Read-only query service for operational outbox visibility."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_events(
        self,
        *,
        status: OutboxEventStatus = OutboxEventStatus.ALL,
        limit: int = 50,
        event_type: str | None = None,
        aggregate_id: str | None = None,
    ) -> list[OutboxEventRecord]:
        if not 1 <= limit <= 100:
            raise ValueError("limit must be between 1 and 100")

        statement = select(OutboxEventModel)

        condition = self._status_condition(status)

        if condition is not None:
            statement = statement.where(condition)

        normalized_event_type = self._normalize_optional(event_type)
        normalized_aggregate_id = self._normalize_optional(aggregate_id)

        if normalized_event_type is not None:
            statement = statement.where(
                OutboxEventModel.event_type == normalized_event_type
            )

        if normalized_aggregate_id is not None:
            statement = statement.where(
                OutboxEventModel.aggregate_id == normalized_aggregate_id
            )

        statement = (
            statement
            .order_by(
                OutboxEventModel.created_at.desc(),
                OutboxEventModel.id.desc(),
            )
            .limit(limit)
        )

        models = list(
            self._session
            .execute(statement)
            .scalars()
            .all()
        )

        return [
            self._to_record(model)
            for model in models
        ]

    def get_summary(self) -> OutboxSummaryRecord:
        pending_condition = self._pending_condition()
        published_condition = self._published_condition()
        failed_condition = self._failed_condition()
        unpublished_condition = (
            OutboxEventModel.published_at.is_(None)
        )

        statement = select(
            func.count(
                OutboxEventModel.id
            ).label("total_count"),
            func.count(
                OutboxEventModel.id
            ).filter(
                pending_condition
            ).label("pending_count"),
            func.count(
                OutboxEventModel.id
            ).filter(
                published_condition
            ).label("published_count"),
            func.count(
                OutboxEventModel.id
            ).filter(
                failed_condition
            ).label("failed_count"),
            func.count(
                OutboxEventModel.id
            ).filter(
                unpublished_condition
            ).label("unpublished_count"),
            func.min(
                OutboxEventModel.created_at
            ).filter(
                unpublished_condition
            ).label("oldest_unpublished_at"),
        )

        row = self._session.execute(statement).one()

        return OutboxSummaryRecord(
            total_count=int(row.total_count),
            pending_count=int(row.pending_count),
            published_count=int(row.published_count),
            failed_count=int(row.failed_count),
            unpublished_count=int(row.unpublished_count),
            oldest_unpublished_at=(
                row.oldest_unpublished_at
            ),
        )

    @classmethod
    def _status_condition(
        cls,
        status: OutboxEventStatus,
    ):
        if status == OutboxEventStatus.ALL:
            return None

        if status == OutboxEventStatus.PENDING:
            return cls._pending_condition()

        if status == OutboxEventStatus.PUBLISHED:
            return cls._published_condition()

        if status == OutboxEventStatus.FAILED:
            return cls._failed_condition()

        raise ValueError(
            f"unsupported outbox status: {status}"
        )

    @staticmethod
    def _pending_condition():
        return and_(
            OutboxEventModel.published_at.is_(None),
            OutboxEventModel.last_error.is_(None),
            OutboxEventModel.attempt_count == 0,
        )

    @staticmethod
    def _published_condition():
        return OutboxEventModel.published_at.is_not(
            None
        )

    @staticmethod
    def _failed_condition():
        return and_(
            OutboxEventModel.published_at.is_(None),
            or_(
                OutboxEventModel.last_error.is_not(
                    None
                ),
                OutboxEventModel.attempt_count > 0,
            ),
        )

    @staticmethod
    def _normalize_optional(
        value: str | None,
    ) -> str | None:
        if value is None:
            return None

        normalized = value.strip()

        return normalized or None

    @classmethod
    def _to_record(
        cls,
        model: OutboxEventModel,
    ) -> OutboxEventRecord:
        return OutboxEventRecord(
            event_id=model.event_id,
            aggregate_type=model.aggregate_type,
            aggregate_id=model.aggregate_id,
            event_type=model.event_type,
            schema_version=model.schema_version,
            source=model.source,
            occurred_at=model.occurred_at,
            created_at=model.created_at,
            published_at=model.published_at,
            attempt_count=model.attempt_count,
            next_attempt_at=model.next_attempt_at,
            last_error=model.last_error,
            locked_by=model.locked_by,
            locked_until=model.locked_until,
            status=cls._resolve_status(model),
        )

    @staticmethod
    def _resolve_status(
        model: OutboxEventModel,
    ) -> OutboxEventStatus:
        if model.published_at is not None:
            return OutboxEventStatus.PUBLISHED

        if (
            model.last_error is not None
            or model.attempt_count > 0
        ):
            return OutboxEventStatus.FAILED

        return OutboxEventStatus.PENDING
