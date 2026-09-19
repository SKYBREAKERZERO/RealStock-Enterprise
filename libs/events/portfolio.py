from __future__ import annotations

from uuid import UUID

from libs.domain.portfolio import (
    Portfolio,
    Position,
)
from libs.events.envelope import EventEnvelope

PORTFOLIO_CREATED = "portfolio.created"
PORTFOLIO_POSITION_ADDED = "portfolio.position.added"

PORTFOLIO_EVENT_SCHEMA_VERSION = 1

PORTFOLIO_API_SOURCE = "portfolio-api"


def create_portfolio_created_event(
    portfolio: Portfolio,
    *,
    source: str = PORTFOLIO_API_SOURCE,
    correlation_id: UUID | None = None,
    causation_id: UUID | None = None,
) -> EventEnvelope[dict[str, object]]:
    """
    Create the canonical portfolio.created integration event.

    Payload values are intentionally JSON-safe so the event can be
    persisted directly into PostgreSQL JSONB by the transactional
    outbox.
    """

    kwargs: dict[str, object] = {
        "event_type": PORTFOLIO_CREATED,
        "schema_version": PORTFOLIO_EVENT_SCHEMA_VERSION,
        "occurred_at": portfolio.created_at,
        "source": source,
        "causation_id": causation_id,
        "payload": {
            "portfolio_id": str(
                portfolio.portfolio_id
            ),
            "user_id": portfolio.user_id,
            "name": portfolio.name,
            "currency": portfolio.currency.value,
            "created_at": (
                portfolio.created_at.isoformat()
            ),
        },
    }

    if correlation_id is not None:
        kwargs["correlation_id"] = (
            correlation_id
        )

    return EventEnvelope(**kwargs)


def create_position_added_event(
    *,
    portfolio_id: UUID,
    position: Position,
    source: str = PORTFOLIO_API_SOURCE,
    correlation_id: UUID | None = None,
    causation_id: UUID | None = None,
) -> EventEnvelope[dict[str, object]]:
    """
    Create the canonical portfolio.position.added integration event.

    Decimal and UUID values are converted to strings so the payload
    is safe for direct JSONB persistence.
    """

    kwargs: dict[str, object] = {
        "event_type": PORTFOLIO_POSITION_ADDED,
        "schema_version": PORTFOLIO_EVENT_SCHEMA_VERSION,
        "occurred_at": position.created_at,
        "source": source,
        "causation_id": causation_id,
        "payload": {
            "portfolio_id": str(
                portfolio_id
            ),
            "position_id": str(
                position.position_id
            ),
            "symbol": position.symbol,
            "market": position.market.value,
            "quantity": str(
                position.quantity
            ),
            "average_cost": str(
                position.average_cost
            ),
            "created_at": (
                position.created_at.isoformat()
            ),
        },
    }

    if correlation_id is not None:
        kwargs["correlation_id"] = (
            correlation_id
        )

    return EventEnvelope(**kwargs)