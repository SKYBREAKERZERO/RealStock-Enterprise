from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from libs.events import (
    RISK_ALERT_DETECTED,
    EventEnvelope,
)
from services.alert_worker.models import (
    AlertQueueMessage,
)

EVENTBRIDGE_RISK_SOURCE = (
    "realstock.risk-engine"
)


class InvalidAlertMessageError(ValueError):
    """
    Raised when an SQS message cannot be interpreted as
    a valid RealStock risk-alert EventBridge message.
    """


class AlertMessageParser:
    """
    Parse an SQS message containing an EventBridge event
    whose detail is the canonical RealStock EventEnvelope.
    """

    def parse(
        self,
        message: dict[str, Any],
    ) -> AlertQueueMessage:
        body = message.get(
            "Body"
        )

        if not isinstance(
            body,
            str,
        ):
            raise InvalidAlertMessageError(
                "SQS message Body must be a string"
            )

        try:
            outer_event = json.loads(
                body
            )
        except json.JSONDecodeError as exc:
            raise InvalidAlertMessageError(
                "SQS message Body is not valid JSON"
            ) from exc

        if not isinstance(
            outer_event,
            dict,
        ):
            raise InvalidAlertMessageError(
                "EventBridge event must be an object"
            )

        source = outer_event.get(
            "source"
        )

        detail_type = outer_event.get(
            "detail-type"
        )

        detail = outer_event.get(
            "detail"
        )

        if (
            source
            != EVENTBRIDGE_RISK_SOURCE
        ):
            raise InvalidAlertMessageError(
                "unexpected EventBridge source"
            )

        if (
            detail_type
            != RISK_ALERT_DETECTED
        ):
            raise InvalidAlertMessageError(
                "unexpected EventBridge detail-type"
            )

        if not isinstance(
            detail,
            dict,
        ):
            raise InvalidAlertMessageError(
                "EventBridge detail must be an object"
            )

        try:
            event = (
                EventEnvelope.model_validate(
                    detail
                )
            )
        except ValidationError as exc:
            raise InvalidAlertMessageError(
                "EventBridge detail is not a valid "
                "RealStock EventEnvelope"
            ) from exc

        if (
            event.event_type
            != RISK_ALERT_DETECTED
        ):
            raise InvalidAlertMessageError(
                "inner event_type must be "
                "risk.alert.detected"
            )

        return AlertQueueMessage(
            source=source,
            detail_type=detail_type,
            detail=event,
        )