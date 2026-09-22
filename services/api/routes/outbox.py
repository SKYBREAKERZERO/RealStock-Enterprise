from __future__ import annotations

from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    Query,
)
from sqlalchemy.orm import Session

from libs.database import get_db_session
from services.api.dependencies import (
    get_current_user_id,
)
from services.api.outbox import (
    OutboxEventStatus,
    OutboxQueryService,
)
from services.api.schemas.outbox import (
    OutboxEventListResponse,
    OutboxEventResponse,
    OutboxSummaryResponse,
)

router = APIRouter(
    prefix="/api/v1/outbox",
    tags=["outbox"],
)


@router.get(
    "/events",
    response_model=OutboxEventListResponse,
)
def list_outbox_events(
    session: Annotated[
        Session,
        Depends(get_db_session),
    ],
    _current_user_id: Annotated[
        str,
        Depends(get_current_user_id),
    ],
    status_filter: Annotated[
        OutboxEventStatus,
        Query(alias="status"),
    ] = OutboxEventStatus.ALL,
    limit: Annotated[
        int,
        Query(ge=1, le=100),
    ] = 50,
    event_type: Annotated[
        str | None,
        Query(max_length=128),
    ] = None,
    aggregate_id: Annotated[
        str | None,
        Query(max_length=128),
    ] = None,
) -> OutboxEventListResponse:
    service = OutboxQueryService(session)

    records = service.list_events(
        status=status_filter,
        limit=limit,
        event_type=event_type,
        aggregate_id=aggregate_id,
    )

    items = [
        OutboxEventResponse(
            event_id=record.event_id,
            aggregate_type=record.aggregate_type,
            aggregate_id=record.aggregate_id,
            event_type=record.event_type,
            schema_version=record.schema_version,
            source=record.source,
            occurred_at=record.occurred_at,
            created_at=record.created_at,
            published_at=record.published_at,
            attempt_count=record.attempt_count,
            next_attempt_at=record.next_attempt_at,
            last_error=record.last_error,
            locked_by=record.locked_by,
            locked_until=record.locked_until,
            status=record.status,
        )
        for record in records
    ]

    return OutboxEventListResponse(
        items=items,
        count=len(items),
        status_filter=status_filter,
    )


@router.get(
    "/summary",
    response_model=OutboxSummaryResponse,
)
def get_outbox_summary(
    session: Annotated[
        Session,
        Depends(get_db_session),
    ],
    _current_user_id: Annotated[
        str,
        Depends(get_current_user_id),
    ],
) -> OutboxSummaryResponse:
    service = OutboxQueryService(session)
    summary = service.get_summary()

    return OutboxSummaryResponse(
        total_count=summary.total_count,
        pending_count=summary.pending_count,
        published_count=summary.published_count,
        failed_count=summary.failed_count,
        unpublished_count=summary.unpublished_count,
        oldest_unpublished_at=(
            summary.oldest_unpublished_at
        ),
    )
