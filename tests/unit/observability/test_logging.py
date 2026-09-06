from __future__ import annotations

import json
import logging

import pytest

from libs.observability import (
    JsonLogFormatter,
    bind_observability_context,
    log_event,
)

pytestmark = pytest.mark.unit


def build_record(
    *,
    message: str = "test message",
) -> logging.LogRecord:
    return logging.LogRecord(
        name="realstock.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )


def test_json_formatter_emits_required_fields() -> None:
    formatter = JsonLogFormatter(
        service_name="risk-engine",
        environment="local",
    )

    payload = json.loads(
        formatter.format(
            build_record()
        )
    )

    assert (
        payload["level"]
        == "INFO"
    )

    assert (
        payload["logger"]
        == "realstock.test"
    )

    assert (
        payload["service"]
        == "risk-engine"
    )

    assert (
        payload["environment"]
        == "local"
    )

    assert (
        payload["message"]
        == "test message"
    )

    assert payload["timestamp"]


def test_json_formatter_includes_trace_context() -> None:
    formatter = JsonLogFormatter(
        service_name="risk-engine",
    )

    with bind_observability_context(
        correlation_id="corr-001",
        event_id="event-001",
        causation_id="cause-001",
    ):
        payload = json.loads(
            formatter.format(
                build_record()
            )
        )

    assert (
        payload["correlation_id"]
        == "corr-001"
    )

    assert (
        payload["event_id"]
        == "event-001"
    )

    assert (
        payload["causation_id"]
        == "cause-001"
    )


def test_json_formatter_omits_empty_context() -> None:
    formatter = JsonLogFormatter(
        service_name="risk-engine",
    )

    payload = json.loads(
        formatter.format(
            build_record()
        )
    )

    assert (
        "correlation_id"
        not in payload
    )

    assert (
        "event_id"
        not in payload
    )

    assert (
        "causation_id"
        not in payload
    )


def test_structured_fields_are_included(
    caplog,
) -> None:
    logger = logging.getLogger(
        "realstock.test.structured"
    )

    with caplog.at_level(
        logging.INFO
    ):
        log_event(
            logger,
            logging.INFO,
            "risk detected",
            symbol="AAPL",
            severity="CRITICAL",
        )

    record = caplog.records[-1]

    fields = record.structured_fields

    assert (
        fields["symbol"]
        == "AAPL"
    )

    assert (
        fields["severity"]
        == "CRITICAL"
    )


def test_invalid_service_name_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="service_name",
    ):
        JsonLogFormatter(
            service_name=" "
        )


def test_invalid_environment_is_rejected() -> None:
    with pytest.raises(
        ValueError,
        match="environment",
    ):
        JsonLogFormatter(
            service_name="risk-engine",
            environment=" ",
        )