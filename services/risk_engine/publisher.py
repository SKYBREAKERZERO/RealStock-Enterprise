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
from libs.observability.propagation import (
    inject_trace_context,
)

DEFAULT_EVENT_BUS_NAME = (
    "default"
)

EVENTBRIDGE_RISK_SOURCE = (
    "realstock.risk-engine"
)


@dataclass(
    frozen=True,
)
class EventBridgePublishResult:
    event_id: str


class EventBridgeRiskEventPublisher:
    """
    Publish canonical RealStock risk events to
    Amazon EventBridge.

    Business event identity is preserved:

        event_id
        correlation_id
        causation_id

    When an OpenTelemetry span is active, its W3C trace
    context is injected into an outbound copy of the event.

    The caller's EventEnvelope remains immutable and is not
    modified.
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

    @staticmethod
    def _prepare_outbound_event(
        event: EventEnvelope,
    ) -> EventEnvelope:
        trace_context = (
            inject_trace_context()
        )

        if not trace_context:
            return event

        return event.model_copy(
            update={
                "trace_context":
                    trace_context
            }
        )

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

        outbound_event = (
            self._prepare_outbound_event(
                event
            )
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
                            outbound_event
                            .to_event_json()
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