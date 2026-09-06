from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from libs.events import EventEnvelope
from services.risk_engine.publisher import (
    EventBridgeRiskEventPublisher,
)
from services.risk_engine.service import (
    RiskEngineService,
)


class InvalidKinesisMarketEventError(ValueError):
    """Raised when a Kinesis record cannot be decoded."""


@dataclass(
    frozen=True,
    slots=True,
)
class KinesisRiskProcessingResult:
    market_event_id: str
    risk_event_id: str | None = None
    eventbridge_event_id: str | None = None

    @property
    def alert_generated(self) -> bool:
        return self.risk_event_id is not None


class KinesisRiskEngineConsumer:
    """
    Application-side adapter between Kinesis records
    and the Risk Engine.

    Flow:

        Kinesis record
            ↓
        EventEnvelope
            ↓
        RiskEngineService
            ↓
        risk.alert.detected
            ↓
        EventBridge
    """

    def __init__(
        self,
        *,
        risk_engine: RiskEngineService,
        publisher: EventBridgeRiskEventPublisher,
    ) -> None:
        self._risk_engine = risk_engine
        self._publisher = publisher

    @staticmethod
    def _decode_data(
        record: Mapping[str, Any],
    ) -> str:
        if "Data" not in record:
            raise InvalidKinesisMarketEventError(
                "Kinesis record does not contain Data"
            )

        raw_data = record["Data"]

        if isinstance(raw_data, bytes):
            try:
                return raw_data.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise InvalidKinesisMarketEventError(
                    "Kinesis Data is not valid UTF-8"
                ) from exc

        if isinstance(raw_data, str):
            return raw_data

        raise InvalidKinesisMarketEventError(
            "Kinesis Data must be bytes or string"
        )

    @staticmethod
    def _parse_event(
        text: str,
    ) -> EventEnvelope:
        try:
            return EventEnvelope.model_validate_json(
                text
            )
        except ValidationError as exc:
            raise InvalidKinesisMarketEventError(
                "Kinesis Data is not a valid EventEnvelope"
            ) from exc

    def process_record(
        self,
        record: Mapping[str, Any],
    ) -> KinesisRiskProcessingResult:
        text = self._decode_data(
            record
        )

        market_event = self._parse_event(
            text
        )

        risk_event = (
            self._risk_engine.process_event(
                market_event
            )
        )

        # Trade event, first quote, or movement below
        # threshold: successfully processed, no alert.
        if risk_event is None:
            return KinesisRiskProcessingResult(
                market_event_id=str(
                    market_event.event_id
                )
            )

        publish_result = (
            self._publisher.publish(
                risk_event
            )
        )

        return KinesisRiskProcessingResult(
            market_event_id=str(
                market_event.event_id
            ),
            risk_event_id=str(
                risk_event.event_id
            ),
            eventbridge_event_id=(
                publish_result.event_id
            ),
        )
    