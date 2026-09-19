from __future__ import annotations

from sqlalchemy.orm import Session

from libs.database.models.outbox import OutboxEventModel
from libs.events.envelope import EventEnvelope


class OutboxRepository:
    """
    SQLAlchemy-backed repository for transactional outbox events.

    Transaction policy:
    - Repository may flush.
    - Repository does NOT commit.
    - Caller owns the transaction boundary.
    """

    def __init__(
        self,
        session: Session,
    ) -> None:
        self._session = session

    def add_event(
        self,
        *,
        aggregate_type: str,
        aggregate_id: str,
        event: EventEnvelope[
            dict[str, object]
        ],
    ) -> OutboxEventModel:
        model = OutboxEventModel(
            event_id=event.event_id,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event.event_type,
            schema_version=event.schema_version,
            source=event.source,
            correlation_id=event.correlation_id,
            causation_id=event.causation_id,
            trace_context=event.trace_context,
            payload=event.payload,
            occurred_at=event.occurred_at,
        )

        self._session.add(model)
        self._session.flush()

        return model