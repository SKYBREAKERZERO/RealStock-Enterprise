from __future__ import annotations

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
    InMemorySpanExporter,
)

from libs.observability.tracing import (
    DEFAULT_INSTRUMENTATION_NAME,
    TraceIdentifiers,
    create_tracing_runtime,
    get_trace_identifiers,
)


def test_create_runtime_builds_tracer() -> None:
    exporter = InMemorySpanExporter()

    runtime = create_tracing_runtime(
        service_name="risk-engine",
        environment="test",
        exporter=exporter,
    )

    try:
        assert runtime.provider is not None
        assert runtime.tracer is not None
    finally:
        runtime.shutdown()


def test_runtime_exports_finished_span() -> None:
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
            pass

        assert runtime.force_flush()

        spans = exporter.get_finished_spans()

        assert len(spans) == 1
        assert spans[0].name == "risk.process"
    finally:
        runtime.shutdown()


def test_runtime_attaches_resource_attributes() -> None:
    exporter = InMemorySpanExporter()

    runtime = create_tracing_runtime(
        service_name="risk-engine",
        environment="staging",
        exporter=exporter,
    )

    try:
        with runtime.tracer.start_as_current_span(
            "risk.process",
        ):
            pass

        assert runtime.force_flush()

        spans = exporter.get_finished_spans()

        assert len(spans) == 1

        attributes = spans[0].resource.attributes

        assert (
            attributes["service.name"]
            == "risk-engine"
        )

        assert (
            attributes[
                "deployment.environment.name"
            ]
            == "staging"
        )
    finally:
        runtime.shutdown()


def test_trace_identifiers_are_available_inside_span() -> None:
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

            assert isinstance(
                identifiers,
                TraceIdentifiers,
            )

            assert (
                len(identifiers.trace_id)
                == 32
            )

            assert (
                len(identifiers.span_id)
                == 16
            )

            int(
                identifiers.trace_id,
                16,
            )

            int(
                identifiers.span_id,
                16,
            )
    finally:
        runtime.shutdown()


def test_trace_identifiers_are_none_without_active_span() -> None:
    assert get_trace_identifiers() is None


def test_explicit_span_can_supply_trace_identifiers() -> None:
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
            identifiers = (
                get_trace_identifiers(
                    span
                )
            )

            assert identifiers is not None
            assert len(
                identifiers.trace_id
            ) == 32
            assert len(
                identifiers.span_id
            ) == 16
    finally:
        runtime.shutdown()


def test_child_span_preserves_trace_id() -> None:
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
            parent_identifiers = (
                get_trace_identifiers()
            )

            assert (
                parent_identifiers
                is not None
            )

            with (
                runtime.tracer
                .start_as_current_span(
                    "eventbridge.publish"
                )
            ):
                child_identifiers = (
                    get_trace_identifiers()
                )

                assert (
                    child_identifiers
                    is not None
                )

                assert (
                    child_identifiers
                    .trace_id
                    == parent_identifiers
                    .trace_id
                )

                assert (
                    child_identifiers
                    .span_id
                    != parent_identifiers
                    .span_id
                )

        assert runtime.force_flush()

        spans = exporter.get_finished_spans()

        assert len(spans) == 2
    finally:
        runtime.shutdown()


def test_child_span_parent_matches_root_span() -> None:
    exporter = InMemorySpanExporter()

    runtime = create_tracing_runtime(
        service_name="risk-engine",
        environment="test",
        exporter=exporter,
    )

    try:
        with runtime.tracer.start_as_current_span(
            "risk.process",
        ) as parent_span:
            parent_span_id = (
                parent_span
                .get_span_context()
                .span_id
            )

            with (
                runtime.tracer
                .start_as_current_span(
                    "eventbridge.publish"
                )
            ):
                pass

        assert runtime.force_flush()

        spans = {
            span.name: span
            for span
            in exporter.get_finished_spans()
        }

        child = spans[
            "eventbridge.publish"
        ]

        assert child.parent is not None

        assert (
            child.parent.span_id
            == parent_span_id
        )
    finally:
        runtime.shutdown()


def test_zero_sampling_ratio_does_not_export_root_span() -> None:
    exporter = InMemorySpanExporter()

    runtime = create_tracing_runtime(
        service_name="risk-engine",
        environment="test",
        exporter=exporter,
        sample_ratio=0.0,
    )

    try:
        with runtime.tracer.start_as_current_span(
            "risk.process",
        ) as span:
            assert not span.is_recording()

        assert runtime.force_flush()

        assert (
            exporter.get_finished_spans()
            == ()
        )
    finally:
        runtime.shutdown()


@pytest.mark.parametrize(
    "sample_ratio",
    [
        -0.01,
        1.01,
        float("inf"),
        float("-inf"),
        float("nan"),
    ],
)
def test_invalid_sample_ratio_is_rejected(
    sample_ratio: float,
) -> None:
    exporter = InMemorySpanExporter()

    with pytest.raises(
        ValueError,
        match="sample_ratio",
    ):
        create_tracing_runtime(
            service_name="risk-engine",
            environment="test",
            exporter=exporter,
            sample_ratio=sample_ratio,
        )


@pytest.mark.parametrize(
    ("field_name", "kwargs"),
    [
        (
            "service_name",
            {
                "service_name": "   ",
                "environment": "test",
            },
        ),
        (
            "environment",
            {
                "service_name": (
                    "risk-engine"
                ),
                "environment": "",
            },
        ),
        (
            "instrumentation_name",
            {
                "service_name": (
                    "risk-engine"
                ),
                "environment": "test",
                "instrumentation_name": (
                    "   "
                ),
            },
        ),
    ],
)
def test_required_runtime_values_are_validated(
    field_name: str,
    kwargs: dict[str, str],
) -> None:
    exporter = InMemorySpanExporter()

    with pytest.raises(
        ValueError,
        match=field_name,
    ):
        create_tracing_runtime(
            exporter=exporter,
            **kwargs,
        )


def test_default_instrumentation_name_is_defined() -> None:
    assert (
        DEFAULT_INSTRUMENTATION_NAME
        == "realstock.observability"
    )


def test_force_flush_rejects_invalid_timeout() -> None:
    exporter = InMemorySpanExporter()

    runtime = create_tracing_runtime(
        service_name="risk-engine",
        environment="test",
        exporter=exporter,
    )

    try:
        with pytest.raises(
            ValueError,
            match="timeout_millis",
        ):
            runtime.force_flush(
                timeout_millis=0
            )
    finally:
        runtime.shutdown()