from __future__ import annotations

from dataclasses import dataclass

from botocore.client import BaseClient

from libs.aws import (
    get_eventbridge_client,
)
from libs.events import (
    RISK_ALERT_DETECTED,
    EventEnvelope,
)

DEFAULT_EVENT_BUS_NAME = "default"

EVENTBRIDGE_RISK_SOURCE = (
    "realstock.risk-engine"
)


@dataclass(frozen=True)
class EventBridgePublishResult:
    event_id: str


class EventBridgeRiskEventPublisher:
    """
    Publish canonical RealStock risk events to
    Amazon EventBridge.

    The canonical EventEnvelope is preserved inside
    EventBridge Detail so correlation_id, causation_id,
    schema_version, and domain payload remain intact.
    """

    def __init__(
        self,
        *,
        event_bus_name: str = (
            DEFAULT_EVENT_BUS_NAME
        ),
        client: BaseClient | None = None,
    ) -> None:
        normalized_bus_name = (
            event_bus_name.strip()
        )

        if not normalized_bus_name:
            raise ValueError(
                "event_bus_name must not be empty"
            )

        self._event_bus_name = (
            normalized_bus_name
        )

        self._client = (
            client
            if client is not None
            else get_eventbridge_client()
        )

    @property
    def event_bus_name(
        self,
    ) -> str:
        return self._event_bus_name

    def publish(
        self,
        event: EventEnvelope,
    ) -> EventBridgePublishResult:
        if (
            event.event_type
            != RISK_ALERT_DETECTED
        ):
            raise ValueError(
                "publisher accepts only "
                "risk.alert.detected events"
            )

        response = (
            self._client.put_events(
                Entries=[
                    {
                        "Source": (
                            EVENTBRIDGE_RISK_SOURCE
                        ),
                        "DetailType": (
                            event.event_type
                        ),
                        "Detail": (
                            event.to_event_json()
                        ),
                        "EventBusName": (
                            self._event_bus_name
                        ),
                    }
                ]
            )
        )

        failed_entry_count = int(
            response.get(
                "FailedEntryCount",
                0,
            )
        )

        entries = response.get(
            "Entries",
            [],
        )

        if (
            failed_entry_count
            != 0
            or len(entries) != 1
        ):
            raise RuntimeError(
                "EventBridge failed to "
                "publish risk event"
            )

        entry = entries[0]

        error_code = entry.get(
            "ErrorCode"
        )

        if error_code:
            error_message = entry.get(
                "ErrorMessage",
                "unknown EventBridge error",
            )

            raise RuntimeError(
                "EventBridge publish failed: "
                f"{error_code}: "
                f"{error_message}"
            )

        event_id = entry.get(
            "EventId"
        )

        if not event_id:
            raise RuntimeError(
                "EventBridge publish response "
                "did not contain EventId"
            )

        return EventBridgePublishResult(
            event_id=event_id
        )