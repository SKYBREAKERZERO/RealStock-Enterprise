from __future__ import annotations

import math
from dataclasses import dataclass

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
    OTLPSpanExporter,
)
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import (
    TracerProvider,
)
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SpanExporter,
)
from opentelemetry.sdk.trace.sampling import (
    ParentBased,
    TraceIdRatioBased,
)
from opentelemetry.trace import (
    Span,
    Tracer,
)

DEFAULT_OTLP_TRACES_ENDPOINT = (
    "http://localhost:4318/v1/traces"
)

DEFAULT_INSTRUMENTATION_NAME = (
    "realstock.observability"
)


@dataclass(
    frozen=True,
    slots=True,
)
class TraceIdentifiers:
    """
    Current OpenTelemetry trace identifiers.

    Values use the canonical lowercase hexadecimal
    representation used by W3C Trace Context.

    trace_id:
        32 hexadecimal characters.

    span_id:
        16 hexadecimal characters.
    """

    trace_id: str
    span_id: str


@dataclass(
    frozen=True,
    slots=True,
)
class TracingRuntime:
    """
    Explicit tracing runtime owned by the application.

    The runtime deliberately does not replace the global
    OpenTelemetry TracerProvider.

    This keeps dependency injection deterministic and avoids
    test pollution caused by OpenTelemetry's process-global
    provider registration.

    Future framework auto-instrumentation can install a global
    provider separately when required.
    """

    provider: TracerProvider
    tracer: Tracer

    def force_flush(
        self,
        timeout_millis: int = 30_000,
    ) -> bool:
        if timeout_millis <= 0:
            raise ValueError(
                "timeout_millis must be positive"
            )

        return self.provider.force_flush(
            timeout_millis=timeout_millis
        )

    def shutdown(
        self,
    ) -> None:
        self.provider.shutdown()


def _normalize_required_value(
    value: str,
    *,
    field_name: str,
) -> str:
    normalized = value.strip()

    if not normalized:
        raise ValueError(
            f"{field_name} must not be empty"
        )

    return normalized


def _validate_sample_ratio(
    sample_ratio: float,
) -> float:
    normalized = float(
        sample_ratio
    )

    if not math.isfinite(
        normalized
    ):
        raise ValueError(
            "sample_ratio must be finite"
        )

    if not 0.0 <= normalized <= 1.0:
        raise ValueError(
            "sample_ratio must be between 0 and 1"
        )

    return normalized


def get_trace_identifiers(
    span: Span | None = None,
) -> TraceIdentifiers | None:
    """
    Return the active trace/span identifiers.

    A non-recording or invalid span produces None.
    """

    active_span = (
        span
        if span is not None
        else trace.get_current_span()
    )

    span_context = (
        active_span.get_span_context()
    )

    if not span_context.is_valid:
        return None

    return TraceIdentifiers(
        trace_id=(
            f"{span_context.trace_id:032x}"
        ),
        span_id=(
            f"{span_context.span_id:016x}"
        ),
    )


def create_tracing_runtime(
    *,
    service_name: str,
    environment: str,
    exporter: SpanExporter | None = None,
    otlp_endpoint: str = (
        DEFAULT_OTLP_TRACES_ENDPOINT
    ),
    sample_ratio: float = 1.0,
    instrumentation_name: str = (
        DEFAULT_INSTRUMENTATION_NAME
    ),
) -> TracingRuntime:
    """
    Build the RealStock production tracing composition.

    Delivery path:

        Application span
            ↓
        BatchSpanProcessor
            ↓
        SpanExporter
            ↓
        OTLP HTTP / ADOT Collector

    An exporter can be injected for tests.

    Production defaults to OTLP/HTTP so services remain
    vendor-neutral. ADOT can later receive OTLP and export
    to AWS X-Ray without coupling application code directly
    to X-Ray APIs.
    """

    normalized_service = (
        _normalize_required_value(
            service_name,
            field_name="service_name",
        )
    )

    normalized_environment = (
        _normalize_required_value(
            environment,
            field_name="environment",
        )
    )

    normalized_instrumentation = (
        _normalize_required_value(
            instrumentation_name,
            field_name="instrumentation_name",
        )
    )

    normalized_ratio = (
        _validate_sample_ratio(
            sample_ratio
        )
    )

    span_exporter: SpanExporter

    if exporter is not None:
        span_exporter = exporter

    else:
        normalized_endpoint = (
            _normalize_required_value(
                otlp_endpoint,
                field_name="otlp_endpoint",
            )
        )

        span_exporter = (
            OTLPSpanExporter(
                endpoint=normalized_endpoint,
            )
        )

    resource = Resource.create(
        {
            "service.name": (
                normalized_service
            ),
            "deployment.environment.name": (
                normalized_environment
            ),
        }
    )

    sampler = ParentBased(
        root=TraceIdRatioBased(
            normalized_ratio
        )
    )

    provider = TracerProvider(
        resource=resource,
        sampler=sampler,
    )

    provider.add_span_processor(
        BatchSpanProcessor(
            span_exporter
        )
    )

    tracer = provider.get_tracer(
        normalized_instrumentation
    )

    return TracingRuntime(
        provider=provider,
        tracer=tracer,
    )