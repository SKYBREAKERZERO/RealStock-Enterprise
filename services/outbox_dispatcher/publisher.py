from __future__ import annotations

from dataclasses import dataclass

from botocore.client import BaseClient

from libs.aws import get_eventbridge_client
from libs.database.repositories.outbox import (
    ClaimedOutboxEvent,
)
from libs.events.envelope import EventEnvelope

DEFAULT_EVENT_BUS_NAME = "default"

EVENTBRIDGE_SOURCE_PREFIX = "realstock."


@dataclass(
    frozen=True,
    slots=True,
)
class EventBridgePublishResult:
    """
    Result returned by Amazon EventBridge.

    event_id is the EventBridge transport event identifier.

    It is not the same identifier as the canonical business
    event_id stored in the transactional outbox.
    """

    event_id: str


class EventBridgeOutboxPublisher:
    """
    Publish claimed transactional outbox events to EventBridge.

    Responsibilities:
    - reconstruct the canonical EventEnvelope;
    - serialize the canonical event contract;
    - publish one event to EventBridge;
    - validate the EventBridge response.

    Non-responsibilities:
    - database transactions;
    - outbox claiming;
    - lease management;
    - retry scheduling;
    - mark_published;
    - mark_failed.

    Delivery semantics are at-least-once.
    """

    def __init__(
        self,
        *,
        event_bus_name: str = DEFAULT_EVENT_BUS_NAME,
        client: BaseClient | None = None,
    ) -> None:
        normalized_event_bus_name = (
            event_bus_name.strip()
        )

        if not normalized_event_bus_name:
            raise ValueError(
                "event_bus_name must not be empty"
            )

        self._event_bus_name = (
            normalized_event_bus_name
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
        event: ClaimedOutboxEvent,
    ) -> EventBridgePublishResult:
        """
        Publish one claimed outbox event.

        The canonical business event identity is preserved inside
        EventBridge Detail.

        EventBridge EventId is transport metadata only.
        """

        canonical_event = (
            self._to_event_envelope(
                event
            )
        )

        eventbridge_source = (
            self._eventbridge_source(
                event.source
            )
        )

        response = (
            self._client.put_events(
                Entries=[
                    {
                        "Source": (
                            eventbridge_source
                        ),
                        "DetailType": (
                            event.event_type
                        ),
                        "Detail": (
                            canonical_event
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
            failed_entry_count != 0
            or len(entries) != 1
        ):
            raise RuntimeError(
                "EventBridge failed to "
                "publish outbox event"
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

        eventbridge_event_id = (
            entry.get(
                "EventId"
            )
        )

        if not eventbridge_event_id:
            raise RuntimeError(
                "EventBridge publish response "
                "did not contain EventId"
            )

        return EventBridgePublishResult(
            event_id=eventbridge_event_id
        )

    @staticmethod
    def _to_event_envelope(
        event: ClaimedOutboxEvent,
    ) -> EventEnvelope[
        dict[str, object]
    ]:
        """
        Reconstruct the canonical RealStock EventEnvelope.

        No new business identity is generated during dispatch.
        """

        return EventEnvelope[
            dict[str, object]
        ](
            event_id=event.event_id,
            event_type=event.event_type,
            schema_version=event.schema_version,
            occurred_at=event.occurred_at,
            source=event.source,
            correlation_id=event.correlation_id,
            causation_id=event.causation_id,
            trace_context=event.trace_context,
            payload=event.payload,
        )

    @staticmethod
    def _eventbridge_source(
        source: str,
    ) -> str:
        """
        Convert a canonical service source into an EventBridge source.

        Example:

            portfolio-api
                ->
            realstock.portfolio-api
        """

        normalized_source = source.strip()

        if not normalized_source:
            raise ValueError(
                "event source must not be empty"
            )

        if normalized_source.startswith(
            EVENTBRIDGE_SOURCE_PREFIX
        ):
            return normalized_source

        return (
            f"{EVENTBRIDGE_SOURCE_PREFIX}"
            f"{normalized_source}"
        )