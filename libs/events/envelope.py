from __future__ import annotations

from datetime import datetime, timezone
from typing import Generic, TypeVar
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


PayloadT = TypeVar("PayloadT")


class EventEnvelope(BaseModel, Generic[PayloadT]):
    """
    Standard event envelope used across RealStock Enterprise.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        str_strip_whitespace=True,
    )

    event_id: UUID = Field(
        default_factory=uuid4,
    )

    event_type: str = Field(
        min_length=3,
        max_length=128,
    )

    schema_version: int = Field(
        default=1,
        ge=1,
    )

    occurred_at: datetime = Field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ),
    )

    source: str = Field(
        min_length=1,
        max_length=128,
    )

    correlation_id: UUID = Field(
        default_factory=uuid4,
    )

    causation_id: UUID | None = None

    payload: PayloadT

    @field_validator("event_type")
    @classmethod
    def validate_event_type(
        cls,
        value: str,
    ) -> str:
        event_type = value.strip().lower()

        if event_type.startswith("."):
            raise ValueError(
                "event_type must not start with '.'"
            )

        if event_type.endswith("."):
            raise ValueError(
                "event_type must not end with '.'"
            )

        if ".." in event_type:
            raise ValueError(
                "event_type must not contain empty segments"
            )

        allowed_characters = set(
            "abcdefghijklmnopqrstuvwxyz"
            "0123456789"
            ".-_"
        )

        if any(
            character not in allowed_characters
            for character in event_type
        ):
            raise ValueError(
                "event_type contains unsupported characters"
            )

        return event_type

    @field_validator("source")
    @classmethod
    def validate_source(
        cls,
        value: str,
    ) -> str:
        source = value.strip().lower()

        if not source:
            raise ValueError(
                "source must not be empty"
            )

        return source

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(
        cls,
        value: datetime,
    ) -> datetime:
        if value.tzinfo is None:
            raise ValueError(
                "occurred_at must be timezone-aware"
            )

        return value.astimezone(
            timezone.utc
        )

    def to_event_dict(
        self,
    ) -> dict[str, object]:
        return self.model_dump(
            mode="json",
        )

    def to_event_json(
        self,
    ) -> str:
        return self.model_dump_json()