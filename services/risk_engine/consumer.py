from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from libs.events import EventEnvelope
from libs.observability import (
    MetricsRecorder,
    bind_observability_context,
    get_logger,
    log_event,
)
from services.risk_engine.publisher import (
    EventBridgeRiskEventPublisher,
)
from services.risk_engine.service import (
    RiskEngineService,
)

LOGGER = get_logger(
    "realstock.risk_engine.consumer"
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

    Observability:

        structured logging
        correlation context
        processing counters
        processing latency
        failure counters
    """

    def __init__(
        self,
        *,
        risk_engine: RiskEngineService,
        publisher: EventBridgeRiskEventPublisher,
        metrics: MetricsRecorder | None = None,
    ) -> None:
        self._risk_engine = risk_engine
        self._publisher = publisher

        self._metrics = (
            metrics
            if metrics is not None
            else MetricsRecorder()
        )

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
                return raw_data.decode(
                    "utf-8"
                )

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
            return (
                EventEnvelope
                .model_validate_json(
                    text
                )
            )

        except ValidationError as exc:
            raise InvalidKinesisMarketEventError(
                "Kinesis Data is not a valid EventEnvelope"
            ) from exc

    def process_record(
        self,
        record: Mapping[str, Any],
    ) -> KinesisRiskProcessingResult:
        """
        Public processing boundary.

        Every attempt records latency.

        Any exception crossing this boundary increments
        RiskProcessingFailures and is propagated to the
        caller so the transport/runtime can apply retry
        semantics.
        """

        with self._metrics.timer(
            "RiskProcessingLatency"
        ):
            try:
                return (
                    self._process_record(
                        record
                    )
                )

            except Exception:
                self._metrics.increment(
                    "RiskProcessingFailures"
                )

                raise

    def _process_record(
        self,
        record: Mapping[str, Any],
    ) -> KinesisRiskProcessingResult:
        text = self._decode_data(
            record
        )

        market_event = (
            self._parse_event(
                text
            )
        )

        market_event_id = str(
            market_event.event_id
        )

        correlation_id = str(
            market_event.correlation_id
        )

        causation_id = (
            str(
                market_event.causation_id
            )
            if market_event.causation_id
            is not None
            else None
        )

        # A market event is considered processed only
        # after it has been successfully decoded and
        # validated as an EventEnvelope.
        self._metrics.increment(
            "MarketEventsProcessed",
            dimensions={
                "EventType": (
                    market_event.event_type
                )
            },
        )

        with bind_observability_context(
            correlation_id=correlation_id,
            event_id=market_event_id,
            causation_id=causation_id,
        ):
            log_event(
                LOGGER,
                logging.INFO,
                "market event received",
                event_type=(
                    market_event.event_type
                ),
            )

            try:
                risk_event = (
                    self._risk_engine
                    .process_event(
                        market_event
                    )
                )

                # Trade event, first quote, stale quote,
                # or movement below configured threshold.
                if risk_event is None:
                    log_event(
                        LOGGER,
                        logging.INFO,
                        (
                            "market event processed "
                            "without risk alert"
                        ),
                        event_type=(
                            market_event.event_type
                        ),
                    )

                    return (
                        KinesisRiskProcessingResult(
                            market_event_id=(
                                market_event_id
                            )
                        )
                    )

                risk_event_id = str(
                    risk_event.event_id
                )

                severity = str(
                    risk_event.payload[
                        "severity"
                    ]
                )

                market = str(
                    risk_event.payload[
                        "market"
                    ]
                )

                # The Risk Engine successfully detected a
                # business risk. Publication may still fail
                # independently afterward.
                self._metrics.increment(
                    "RiskAlertsGenerated",
                    dimensions={
                        "Severity": severity,
                        "Market": market,
                    },
                )

                log_event(
                    LOGGER,
                    logging.WARNING,
                    "risk alert generated",
                    risk_event_id=(
                        risk_event_id
                    ),
                    risk_type=(
                        risk_event.payload.get(
                            "risk_type"
                        )
                    ),
                    severity=severity,
                    market=market,
                    symbol=(
                        risk_event.payload.get(
                            "symbol"
                        )
                    ),
                    observed_value=(
                        risk_event.payload.get(
                            "observed_value"
                        )
                    ),
                    threshold=(
                        risk_event.payload.get(
                            "threshold"
                        )
                    ),
                )

                publish_result = (
                    self._publisher.publish(
                        risk_event
                    )
                )

                # Increment only after EventBridge accepted
                # the publication.
                self._metrics.increment(
                    "RiskEventsPublished",
                    dimensions={
                        "Severity": severity,
                        "Market": market,
                    },
                )

                log_event(
                    LOGGER,
                    logging.INFO,
                    (
                        "risk event published "
                        "to eventbridge"
                    ),
                    risk_event_id=(
                        risk_event_id
                    ),
                    eventbridge_event_id=(
                        publish_result.event_id
                    ),
                )

                return (
                    KinesisRiskProcessingResult(
                        market_event_id=(
                            market_event_id
                        ),
                        risk_event_id=(
                            risk_event_id
                        ),
                        eventbridge_event_id=(
                            publish_result.event_id
                        ),
                    )
                )

            except Exception:
                LOGGER.exception(
                    "risk event processing failed",
                    extra={
                        "structured_fields": {
                            "event_type": (
                                market_event
                                .event_type
                            ),
                        }
                    },
                )

                raise