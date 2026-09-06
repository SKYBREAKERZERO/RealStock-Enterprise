from __future__ import annotations

import pytest

from libs.observability import (
    bind_observability_context,
    get_observability_context,
)

pytestmark = pytest.mark.unit


def test_context_is_empty_by_default() -> None:
    context = (
        get_observability_context()
    )

    assert (
        context.correlation_id
        is None
    )

    assert context.event_id is None

    assert (
        context.causation_id
        is None
    )


def test_context_can_be_bound() -> None:
    with bind_observability_context(
        correlation_id="corr-001",
        event_id="event-001",
        causation_id="cause-001",
    ):
        context = (
            get_observability_context()
        )

        assert (
            context.correlation_id
            == "corr-001"
        )

        assert (
            context.event_id
            == "event-001"
        )

        assert (
            context.causation_id
            == "cause-001"
        )


def test_context_is_restored_after_scope() -> None:
    with bind_observability_context(
        correlation_id="corr-001",
    ):
        assert (
            get_observability_context()
            .correlation_id
            == "corr-001"
        )

    assert (
        get_observability_context()
        .correlation_id
        is None
    )


def test_nested_context_is_restored() -> None:
    with bind_observability_context(
        correlation_id="outer",
    ):
        assert (
            get_observability_context()
            .correlation_id
            == "outer"
        )

        with bind_observability_context(
            correlation_id="inner",
        ):
            assert (
                get_observability_context()
                .correlation_id
                == "inner"
            )

        assert (
            get_observability_context()
            .correlation_id
            == "outer"
        )