from __future__ import annotations

from opentelemetry import trace
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from libs.observability.propagation import (
    TRACEPARENT_HEADER,
    TRACESTATE_HEADER,
    extract_trace_context,
    inject_trace_context,
)
from libs.observability.tracing import (
    create_tracing_runtime,
    get_trace_identifiers,
)


def test_inject_current_trace_context() -> None:
    exporter = InMemorySpanExporter()

    runtime = create_tracing_runtime(
        service_name="risk-engine",
        environment="test",
        exporter=exporter,
    )

    try:
        with runtime.tracer.start_as_current_span(
            "risk.process",
        ):
            carrier = (
                inject_trace_context()
            )

            assert (
                TRACEPARENT_HEADER
                in carrier
            )

            assert carrier[
                TRACEPARENT_HEADER
            ].startswith("00-")
    finally:
        runtime.shutdown()


def test_traceparent_contains_current_trace_and_span_ids() -> None:
    exporter = InMemorySpanExporter()

    runtime = create_tracing_runtime(
        service_name="risk-engine",
        environment="test",
        exporter=exporter,
    )

    try:
        with runtime.tracer.start_as_current_span(
            "risk.process",
        ):
            identifiers = (
                get_trace_identifiers()
            )

            assert identifiers is not None

            carrier = (
                inject_trace_context()
            )

            traceparent = carrier[
                TRACEPARENT_HEADER
            ]

            parts = traceparent.split(
                "-"
            )

            assert len(parts) == 4

            version = parts[0]
            trace_id = parts[1]
            span_id = parts[2]
            flags = parts[3]

            assert version == "00"

            assert (
                trace_id
                == identifiers.trace_id
            )

            assert (
                span_id
                == identifiers.span_id
            )

            assert len(flags) == 2
    finally:
        runtime.shutdown()


def test_explicit_context_can_be_injected() -> None:
    exporter = InMemorySpanExporter()

    runtime = create_tracing_runtime(
        service_name="risk-engine",
        environment="test",
        exporter=exporter,
    )

    try:
        with runtime.tracer.start_as_current_span(
            "risk.process",
        ) as span:
            explicit_context = (
                trace.set_span_in_context(
                    span
                )
            )

            carrier = (
                inject_trace_context(
                    context=(
                        explicit_context
                    )
                )
            )

            assert (
                TRACEPARENT_HEADER
                in carrier
            )
    finally:
        runtime.shutdown()


def test_extract_preserves_remote_trace_id() -> None:
    exporter = InMemorySpanExporter()

    producer_runtime = (
        create_tracing_runtime(
            service_name="risk-engine",
            environment="test",
            exporter=exporter,
        )
    )

    consumer_runtime = (
        create_tracing_runtime(
            service_name="alert-worker",
            environment="test",
            exporter=exporter,
        )
    )

    try:
        with (
            producer_runtime
            .tracer
            .start_as_current_span(
                "eventbridge.publish"
            )
        ):
            producer_identifiers = (
                get_trace_identifiers()
            )

            assert (
                producer_identifiers
                is not None
            )

            carrier = (
                inject_trace_context()
            )

        extracted_context = (
            extract_trace_context(
                carrier
            )
        )

        with (
            consumer_runtime
            .tracer
            .start_as_current_span(
                "alert.process",
                context=(
                    extracted_context
                ),
            )
        ):
            consumer_identifiers = (
                get_trace_identifiers()
            )

            assert (
                consumer_identifiers
                is not None
            )

            assert (
                consumer_identifiers
                .trace_id
                == producer_identifiers
                .trace_id
            )

            assert (
                consumer_identifiers
                .span_id
                != producer_identifiers
                .span_id
            )
    finally:
        producer_runtime.shutdown()
        consumer_runtime.shutdown()


def test_extract_creates_remote_parent_relationship() -> None:
    exporter = InMemorySpanExporter()

    producer_runtime = (
        create_tracing_runtime(
            service_name="risk-engine",
            environment="test",
            exporter=exporter,
        )
    )

    consumer_runtime = (
        create_tracing_runtime(
            service_name="alert-worker",
            environment="test",
            exporter=exporter,
        )
    )

    try:
        with (
            producer_runtime
            .tracer
            .start_as_current_span(
                "eventbridge.publish"
            )
        ) as producer_span:
            producer_span_id = (
                producer_span
                .get_span_context()
                .span_id
            )

            carrier = (
                inject_trace_context()
            )

        extracted_context = (
            extract_trace_context(
                carrier
            )
        )

        with (
            consumer_runtime
            .tracer
            .start_as_current_span(
                "alert.process",
                context=(
                    extracted_context
                ),
            )
        ):
            pass

        assert producer_runtime.force_flush()
        assert consumer_runtime.force_flush()

        spans = (
            exporter.get_finished_spans()
        )

        consumer_span = next(
            span
            for span in spans
            if span.name
            == "alert.process"
        )

        assert (
            consumer_span.parent
            is not None
        )

        assert (
            consumer_span.parent
            .span_id
            == producer_span_id
        )

        assert (
            consumer_span.parent
            .is_remote
        )
    finally:
        producer_runtime.shutdown()
        consumer_runtime.shutdown()


def test_missing_carrier_returns_root_context() -> None:
    context = (
        extract_trace_context(
            None
        )
    )

    span = trace.get_current_span(
        context
    )

    assert not (
        span
        .get_span_context()
        .is_valid
    )


def test_empty_carrier_returns_root_context() -> None:
    context = (
        extract_trace_context(
            {}
        )
    )

    span = trace.get_current_span(
        context
    )

    assert not (
        span
        .get_span_context()
        .is_valid
    )


def test_invalid_traceparent_is_ignored() -> None:
    context = (
        extract_trace_context(
            {
                TRACEPARENT_HEADER: (
                    "invalid"
                )
            }
        )
    )

    span = trace.get_current_span(
        context
    )

    assert not (
        span
        .get_span_context()
        .is_valid
    )


def test_unknown_transport_metadata_is_ignored() -> None:
    context = (
        extract_trace_context(
            {
                "message-id": "abc",
                "event-type": (
                    "risk.alert.detected"
                ),
            }
        )
    )

    span = trace.get_current_span(
        context
    )

    assert not (
        span
        .get_span_context()
        .is_valid
    )


def test_trace_headers_are_case_insensitive() -> None:
    exporter = InMemorySpanExporter()

    runtime = create_tracing_runtime(
        service_name="risk-engine",
        environment="test",
        exporter=exporter,
    )

    try:
        with runtime.tracer.start_as_current_span(
            "risk.process",
        ):
            carrier = (
                inject_trace_context()
            )

        context = (
            extract_trace_context(
                {
                    "TraceParent": carrier[
                        TRACEPARENT_HEADER
                    ]
                }
            )
        )

        span_context = (
            trace.get_current_span(
                context
            ).get_span_context()
        )

        assert span_context.is_valid
    finally:
        runtime.shutdown()


def test_empty_trace_headers_are_ignored() -> None:
    context = (
        extract_trace_context(
            {
                TRACEPARENT_HEADER: " ",
                TRACESTATE_HEADER: "",
            }
        )
    )

    span_context = (
        trace.get_current_span(
            context
        ).get_span_context()
    )

    assert not span_context.is_valid


def test_unknown_headers_are_not_returned_by_injection() -> None:
    exporter = InMemorySpanExporter()

    runtime = create_tracing_runtime(
        service_name="risk-engine",
        environment="test",
        exporter=exporter,
    )

    try:
        with runtime.tracer.start_as_current_span(
            "risk.process",
        ):
            carrier = (
                inject_trace_context()
            )

        assert set(
            carrier
        ).issubset(
            {
                TRACEPARENT_HEADER,
                TRACESTATE_HEADER,
            }
        )
    finally:
        runtime.shutdown()