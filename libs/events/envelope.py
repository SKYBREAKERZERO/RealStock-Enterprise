from __future__ import annotations

from datetime import UTC, datetime
from typing import Generic, TypeVar
from uuid import UUID, uuid4

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)

PayloadT = TypeVar("PayloadT")


class EventEnvelope(
    BaseModel,
    Generic[PayloadT],  # noqa: UP046
):
    """
    Standard event envelope used across RealStock Enterprise.

    Business correlation:

        event_id
        correlation_id
        causation_id

    Distributed tracing:

        trace_context

    trace_context contains transport-neutral W3C Trace Context
    metadata such as traceparent and tracestate.

    It is optional so events created outside an active trace
    preserve the existing serialized event contract.

    Generic payload typing is intentionally preserved because
    existing producers and consumers use EventEnvelope[T] as
    part of the public event API.
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
            UTC
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

    trace_context: (
        dict[str, str] | None
    ) = None

    payload: PayloadT

    @field_validator(
        "event_type"
    )
    @classmethod
    def validate_event_type(
        cls,
        value: str,
    ) -> str:
        event_type = (
            value.strip().lower()
        )

        if event_type.startswith(
            "."
        ):
            raise ValueError(
                "event_type must not start with '.'"
            )

        if event_type.endswith(
            "."
        ):
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
            character
            not in allowed_characters
            for character in event_type
        ):
            raise ValueError(
                "event_type contains unsupported characters"
            )

        return event_type

    @field_validator(
        "source"
    )
    @classmethod
    def validate_source(
        cls,
        value: str,
    ) -> str:
        source = (
            value.strip().lower()
        )

        if not source:
            raise ValueError(
                "source must not be empty"
            )

        return source

    @field_validator(
        "occurred_at"
    )
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
            UTC
        )

    def _serialization_exclude(
        self,
    ) -> set[str]:
        """
        Preserve the pre-tracing wire contract when no trace
        context exists.

        Only trace_context is conditionally omitted. Existing
        nullable fields such as causation_id remain part of
        the established event wire contract.
        """

        if self.trace_context is None:
            return {
                "trace_context"
            }

        return set()

    def to_event_dict(
        self,
    ) -> dict[str, object]:
        return self.model_dump(
            mode="json",
            exclude=(
                self._serialization_exclude()
            ),
        )

    def to_event_json(
        self,
    ) -> str:
        return self.model_dump_json(
            exclude=(
                self._serialization_exclude()
            ),
        )