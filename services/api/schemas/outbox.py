from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from services.api.outbox.status import (
    OutboxEventStatus,
)


class OutboxEventResponse(BaseModel):
    model_config = ConfigDict(
        use_enum_values=True,
    )

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


class OutboxEventListResponse(BaseModel):
    model_config = ConfigDict(
        use_enum_values=True,
    )

    items: list[OutboxEventResponse]
    count: int
    status_filter: OutboxEventStatus


class OutboxSummaryResponse(BaseModel):
    total_count: int
    pending_count: int
    published_count: int
    failed_count: int
    unpublished_count: int
    oldest_unpublished_at: datetime | None
