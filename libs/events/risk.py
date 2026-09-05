from __future__ import annotations

from uuid import UUID

from libs.domain.risk import RiskAlert
from libs.events.envelope import EventEnvelope

RISK_ALERT_DETECTED = (
    "risk.alert.detected"
)

RISK_EVENT_SCHEMA_VERSION = 1

RISK_ENGINE_SOURCE = (
    "risk-engine"
)


def create_risk_alert_event(
    alert: RiskAlert,
    *,
    source: str = RISK_ENGINE_SOURCE,
    correlation_id: UUID | None = None,
    causation_id: UUID | None = None,
) -> EventEnvelope:
    """
    Convert a RiskAlert domain object into the canonical
    risk.alert.detected event contract.

    correlation_id:
        Tracks the complete business/event flow.

    causation_id:
        Identifies the direct upstream event that caused
        this risk alert.
    """

    kwargs: dict[str, object] = {
        "event_type": RISK_ALERT_DETECTED,
        "schema_version": (
            RISK_EVENT_SCHEMA_VERSION
        ),
        "occurred_at": alert.occurred_at,
        "source": source,
        "causation_id": causation_id,
        "payload": alert.model_dump(
            mode="json",
        ),
    }

    if correlation_id is not None:
        kwargs["correlation_id"] = (
            correlation_id
        )

    return EventEnvelope(
        **kwargs
    )