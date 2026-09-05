from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from libs.events import EventEnvelope


class AlertQueueMessage(BaseModel):
    """
    Normalized representation of an EventBridge event
    delivered to the Alert Worker through SQS.

    This model represents the transport boundary only.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )

    source: str = Field(
        min_length=1,
    )

    detail_type: str = Field(
        min_length=1,
    )

    detail: EventEnvelope