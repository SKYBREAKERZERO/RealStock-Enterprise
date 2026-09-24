from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from libs.domain.portfolio import (
    Portfolio,
    Position,
)
from libs.events.envelope import EventEnvelope

PORTFOLIO_CREATED = "portfolio.created"
PORTFOLIO_POSITION_ADDED = "portfolio.position.added"
PORTFOLIO_POSITION_UPDATED = "portfolio.position.updated"
PORTFOLIO_POSITION_REMOVED = "portfolio.position.removed"

PORTFOLIO_EVENT_SCHEMA_VERSION = 1
PORTFOLIO_API_SOURCE = "portfolio-api"


def create_portfolio_created_event(
    portfolio: Portfolio,
    *,
    source: str = PORTFOLIO_API_SOURCE,
    correlation_id: UUID | None = None,
    causation_id: UUID | None = None,
) -> EventEnvelope[dict[str, object]]:
    kwargs: dict[str, object] = {
        "event_type": PORTFOLIO_CREATED,
        "schema_version": PORTFOLIO_EVENT_SCHEMA_VERSION,
        "occurred_at": portfolio.created_at,
        "source": source,
        "causation_id": causation_id,
        "payload": {
            "portfolio_id": str(portfolio.portfolio_id),
            "user_id": portfolio.user_id,
            "name": portfolio.name,
            "currency": portfolio.currency.value,
            "created_at": portfolio.created_at.isoformat(),
        },
    }

    if correlation_id is not None:
        kwargs["correlation_id"] = correlation_id

    return EventEnvelope(**kwargs)


def create_position_added_event(
    *,
    portfolio_id: UUID,
    position: Position,
    source: str = PORTFOLIO_API_SOURCE,
    correlation_id: UUID | None = None,
    causation_id: UUID | None = None,
) -> EventEnvelope[dict[str, object]]:
    kwargs: dict[str, object] = {
        "event_type": PORTFOLIO_POSITION_ADDED,
        "schema_version": PORTFOLIO_EVENT_SCHEMA_VERSION,
        "occurred_at": position.created_at,
        "source": source,
        "causation_id": causation_id,
        "payload": {
            "portfolio_id": str(portfolio_id),
            "position_id": str(position.position_id),
            "symbol": position.symbol,
            "market": position.market.value,
            "quantity": str(position.quantity),
            "average_cost": str(position.average_cost),
            "created_at": position.created_at.isoformat(),
        },
    }

    if correlation_id is not None:
        kwargs["correlation_id"] = correlation_id

    return EventEnvelope(**kwargs)


def create_position_updated_event(
    *,
    portfolio_id: UUID,
    previous_position: Position,
    position: Position,
    source: str = PORTFOLIO_API_SOURCE,
    correlation_id: UUID | None = None,
    causation_id: UUID | None = None,
) -> EventEnvelope[dict[str, object]]:
    kwargs: dict[str, object] = {
        "event_type": PORTFOLIO_POSITION_UPDATED,
        "schema_version": PORTFOLIO_EVENT_SCHEMA_VERSION,
        "occurred_at": position.updated_at,
        "source": source,
        "causation_id": causation_id,
        "payload": {
            "portfolio_id": str(portfolio_id),
            "position_id": str(position.position_id),
            "symbol": position.symbol,
            "market": position.market.value,
            "previous_quantity": str(previous_position.quantity),
            "quantity": str(position.quantity),
            "previous_average_cost": str(previous_position.average_cost),
            "average_cost": str(position.average_cost),
            "updated_at": position.updated_at.isoformat(),
        },
    }

    if correlation_id is not None:
        kwargs["correlation_id"] = correlation_id

    return EventEnvelope(**kwargs)


def create_position_removed_event(
    *,
    portfolio_id: UUID,
    position: Position,
    removed_at: datetime | None = None,
    source: str = PORTFOLIO_API_SOURCE,
    correlation_id: UUID | None = None,
    causation_id: UUID | None = None,
) -> EventEnvelope[dict[str, object]]:
    event_time = removed_at or datetime.now(UTC)

    if event_time.tzinfo is None:
        raise ValueError("removed_at must be timezone-aware")

    event_time = event_time.astimezone(UTC)

    kwargs: dict[str, object] = {
        "event_type": PORTFOLIO_POSITION_REMOVED,
        "schema_version": PORTFOLIO_EVENT_SCHEMA_VERSION,
        "occurred_at": event_time,
        "source": source,
        "causation_id": causation_id,
        "payload": {
            "portfolio_id": str(portfolio_id),
            "position_id": str(position.position_id),
            "symbol": position.symbol,
            "market": position.market.value,
            "quantity": str(position.quantity),
            "average_cost": str(position.average_cost),
            "removed_at": event_time.isoformat(),
        },
    }

    if correlation_id is not None:
        kwargs["correlation_id"] = correlation_id

    return EventEnvelope(**kwargs)
