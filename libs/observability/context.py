from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

_correlation_id: ContextVar[str | None] = ContextVar(
    "correlation_id",
    default=None,
)

_event_id: ContextVar[str | None] = ContextVar(
    "event_id",
    default=None,
)

_causation_id: ContextVar[str | None] = ContextVar(
    "causation_id",
    default=None,
)


@dataclass(
    frozen=True,
    slots=True,
)
class ObservabilityContext:
    """
    Immutable snapshot of the current observability context.

    The context is propagated through ContextVar so callers
    do not need to explicitly pass correlation and event
    identifiers through every application layer.
    """

    correlation_id: str | None = None
    event_id: str | None = None
    causation_id: str | None = None


def get_observability_context(
) -> ObservabilityContext:
    """
    Return a snapshot of the currently bound context.
    """

    return ObservabilityContext(
        correlation_id=(
            _correlation_id.get()
        ),
        event_id=(
            _event_id.get()
        ),
        causation_id=(
            _causation_id.get()
        ),
    )


@contextmanager
def bind_observability_context(
    *,
    correlation_id: str | None = None,
    event_id: str | None = None,
    causation_id: str | None = None,
) -> Iterator[None]:
    """
    Bind observability identifiers for the current execution
    context and restore the previous values when the scope
    exits.

    ContextVar makes this safe for nested scopes and future
    asynchronous request/task execution.
    """

    correlation_token = (
        _correlation_id.set(
            correlation_id
        )
    )

    event_token = (
        _event_id.set(
            event_id
        )
    )

    causation_token = (
        _causation_id.set(
            causation_id
        )
    )

    try:
        yield

    finally:
        _causation_id.reset(
            causation_token
        )

        _event_id.reset(
            event_token
        )

        _correlation_id.reset(
            correlation_token
        )