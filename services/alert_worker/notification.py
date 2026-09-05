from __future__ import annotations

import json
from dataclasses import dataclass

from botocore.client import BaseClient

from libs.aws import get_sns_client
from libs.domain.risk import RiskAlert
from libs.events import (
    RISK_ALERT_DETECTED,
    EventEnvelope,
)


@dataclass(frozen=True)
class SnsPublishResult:
    message_id: str


class RiskNotificationFormatter:
    """
    Convert a canonical risk event into a notification
    suitable for SNS subscribers.

    Formatting is kept separate from SNS transport so it can
    later be reused by SES, Slack, webhook, or other channels.
    """

    def format_subject(
        self,
        *,
        event: EventEnvelope,
    ) -> str:
        alert = self._parse_alert(
            event=event
        )

        return (
            "[RealStock] "
            f"{alert.severity.value} "
            f"{alert.market.value}:"
            f"{alert.symbol}"
        )

    def format_message(
        self,
        *,
        event: EventEnvelope,
    ) -> str:
        alert = self._parse_alert(
            event=event
        )

        notification = {
            "notification_type": (
                "risk_alert"
            ),
            "event_id": str(
                event.event_id
            ),
            "correlation_id": str(
                event.correlation_id
            ),
            "causation_id": (
                str(event.causation_id)
                if event.causation_id
                is not None
                else None
            ),
            "occurred_at": (
                event.occurred_at.isoformat()
            ),
            "risk_type": (
                alert.risk_type.value
            ),
            "severity": (
                alert.severity.value
            ),
            "market": (
                alert.market.value
            ),
            "symbol": alert.symbol,
            "observed_value": str(
                alert.observed_value
            ),
            "threshold": str(
                alert.threshold
            ),
            "message": alert.message,
        }

        return json.dumps(
            notification,
            ensure_ascii=False,
            separators=(",", ":"),
        )

    @staticmethod
    def _parse_alert(
        *,
        event: EventEnvelope,
    ) -> RiskAlert:
        if (
            event.event_type
            != RISK_ALERT_DETECTED
        ):
            raise ValueError(
                "notification formatter accepts only "
                "risk.alert.detected events"
            )

        return RiskAlert.model_validate(
            event.payload
        )


class SnsRiskNotificationPublisher:
    """
    Publish validated risk notifications through Amazon SNS.

    SNS failures are intentionally allowed to propagate.
    The Alert Worker must not acknowledge/delete the SQS
    message when downstream notification delivery fails.
    """

    def __init__(
        self,
        *,
        topic_arn: str,
        client: BaseClient | None = None,
        formatter: (
            RiskNotificationFormatter
            | None
        ) = None,
    ) -> None:
        normalized_topic_arn = (
            topic_arn.strip()
        )

        if not normalized_topic_arn:
            raise ValueError(
                "topic_arn must not be empty"
            )

        self._topic_arn = (
            normalized_topic_arn
        )

        self._client = (
            client
            if client is not None
            else get_sns_client()
        )

        self._formatter = (
            formatter
            if formatter is not None
            else RiskNotificationFormatter()
        )

    @property
    def topic_arn(
        self,
    ) -> str:
        return self._topic_arn

    def publish(
        self,
        event: EventEnvelope,
    ) -> SnsPublishResult:
        alert = RiskAlert.model_validate(
            event.payload
        )

        subject = (
            self._formatter.format_subject(
                event=event
            )
        )

        message = (
            self._formatter.format_message(
                event=event
            )
        )

        response = self._client.publish(
            TopicArn=self._topic_arn,
            Subject=subject,
            Message=message,
            MessageAttributes={
                "severity": {
                    "DataType": "String",
                    "StringValue": (
                        alert.severity.value
                    ),
                },
                "risk_type": {
                    "DataType": "String",
                    "StringValue": (
                        alert.risk_type.value
                    ),
                },
                "market": {
                    "DataType": "String",
                    "StringValue": (
                        alert.market.value
                    ),
                },
                "symbol": {
                    "DataType": "String",
                    "StringValue": (
                        alert.symbol
                    ),
                },
                "correlation_id": {
                    "DataType": "String",
                    "StringValue": str(
                        event.correlation_id
                    ),
                },
            },
        )

        message_id = response.get(
            "MessageId"
        )

        if not message_id:
            raise RuntimeError(
                "SNS publish response did not "
                "contain MessageId"
            )

        return SnsPublishResult(
            message_id=message_id
        )