from __future__ import annotations

from collections.abc import (
    Mapping,
)
from typing import Any

from opentelemetry.context import (
    Context,
)
from opentelemetry.propagate import (
    extract,
    inject,
)

TRACEPARENT_HEADER = "traceparent"
TRACESTATE_HEADER = "tracestate"

SUPPORTED_TRACE_HEADERS = frozenset(
    {
        TRACEPARENT_HEADER,
        TRACESTATE_HEADER,
    }
)


def _normalize_carrier(
    carrier: Mapping[str, Any] | None,
) -> dict[str, str]:
    """
    Normalize an external trace carrier.

    Only W3C tracing headers are retained. Unknown transport
    metadata is deliberately ignored.
    """

    if carrier is None:
        return {}

    normalized: dict[str, str] = {}

    for raw_key, raw_value in (
        carrier.items()
    ):
        key = str(
            raw_key
        ).strip().lower()

        if (
            key
            not in SUPPORTED_TRACE_HEADERS
        ):
            continue

        if raw_value is None:
            continue

        value = str(
            raw_value
        ).strip()

        if not value:
            continue

        normalized[key] = value

    return normalized


def inject_trace_context(
    *,
    context: Context | None = None,
) -> dict[str, str]:
    """
    Serialize the current OpenTelemetry context into a
    transport-neutral W3C trace carrier.

    The returned mapping can be placed in an EventEnvelope,
    message attribute, HTTP header set, or another asynchronous
    transport.
    """

    carrier: dict[str, str] = {}

    inject(
        carrier,
        context=context,
    )

    return _normalize_carrier(
        carrier
    )


def extract_trace_context(
    carrier: Mapping[str, Any] | None,
) -> Context:
    """
    Extract W3C Trace Context from an external carrier.

    Invalid or missing trace headers are handled by the
    OpenTelemetry propagator as an empty/root context rather
    than a business-processing failure.
    """

    normalized = (
        _normalize_carrier(
            carrier
        )
    )

    return extract(
        normalized
    )