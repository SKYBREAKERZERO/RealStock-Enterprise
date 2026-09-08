from __future__ import annotations

import json
import logging
import sys
from datetime import (
    UTC,
    datetime,
)
from typing import Any

from libs.observability.context import (
    get_observability_context,
)
from libs.observability.tracing import (
    get_trace_identifiers,
)

DEFAULT_SERVICE_NAME = (
    "realstock"
)


RESERVED_LOG_FIELDS = frozenset(
    {
        "timestamp",
        "level",
        "logger",
        "service",
        "environment",
        "message",
        "correlation_id",
        "event_id",
        "causation_id",
        "trace_id",
        "span_id",
        "exception",
    }
)


class JsonLogFormatter(
    logging.Formatter
):
    """
    CloudWatch-friendly structured JSON formatter.

    Logs are emitted as single-line JSON and can later be
    collected by ECS awslogs, FireLens, Fluent Bit,
    OpenTelemetry Collector, or other log pipelines.

    Business correlation identifiers and OpenTelemetry trace
    identifiers are emitted together when available:

        correlation_id
        event_id
        causation_id
        trace_id
        span_id

    Business identifiers describe event causality while
    trace_id/span_id describe the distributed execution path.
    """

    def __init__(
        self,
        *,
        service_name: str = (
            DEFAULT_SERVICE_NAME
        ),
        environment: str = "local",
    ) -> None:
        super().__init__()

        normalized_service = (
            service_name.strip()
        )

        normalized_environment = (
            environment.strip()
        )

        if not normalized_service:
            raise ValueError(
                "service_name must not be empty"
            )

        if not normalized_environment:
            raise ValueError(
                "environment must not be empty"
            )

        self._service_name = (
            normalized_service
        )

        self._environment = (
            normalized_environment
        )

    def format(
        self,
        record: logging.LogRecord,
    ) -> str:
        context = (
            get_observability_context()
        )

        trace_identifiers = (
            get_trace_identifiers()
        )

        payload: dict[str, Any] = {
            "timestamp": (
                datetime.now(
                    UTC
                ).isoformat()
            ),
            "level": record.levelname,
            "logger": record.name,
            "service": (
                self._service_name
            ),
            "environment": (
                self._environment
            ),
            "message": (
                record.getMessage()
            ),
        }

        # ====================================================
        # Business / event correlation context
        # ====================================================

        if (
            context.correlation_id
            is not None
        ):
            payload[
                "correlation_id"
            ] = context.correlation_id

        if (
            context.event_id
            is not None
        ):
            payload[
                "event_id"
            ] = context.event_id

        if (
            context.causation_id
            is not None
        ):
            payload[
                "causation_id"
            ] = context.causation_id

        # ====================================================
        # Distributed trace context
        #
        # These values come from the active OpenTelemetry span
        # and therefore must not be supplied by callers.
        # ====================================================

        if (
            trace_identifiers
            is not None
        ):
            payload[
                "trace_id"
            ] = (
                trace_identifiers
                .trace_id
            )

            payload[
                "span_id"
            ] = (
                trace_identifiers
                .span_id
            )

        # ====================================================
        # Exception
        # ====================================================

        if record.exc_info:
            payload[
                "exception"
            ] = self.formatException(
                record.exc_info
            )

        # ====================================================
        # Structured application fields
        #
        # Reserved observability fields cannot be overridden
        # by arbitrary structured log data.
        # ====================================================

        extra_fields = getattr(
            record,
            "structured_fields",
            None,
        )

        if isinstance(
            extra_fields,
            dict,
        ):
            for key, value in (
                extra_fields.items()
            ):
                if (
                    key
                    in RESERVED_LOG_FIELDS
                ):
                    continue

                payload[key] = value

        return json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )


def configure_json_logging(
    *,
    service_name: str = (
        DEFAULT_SERVICE_NAME
    ),
    environment: str = "local",
    level: int = logging.INFO,
) -> None:
    """
    Configure process-wide JSON logging.

    Logs are written to stdout so container runtimes can
    forward them to CloudWatch Logs, FireLens, Fluent Bit,
    ADOT, or another centralized logging pipeline.
    """

    handler = logging.StreamHandler(
        sys.stdout
    )

    handler.setFormatter(
        JsonLogFormatter(
            service_name=service_name,
            environment=environment,
        )
    )

    root_logger = (
        logging.getLogger()
    )

    root_logger.handlers.clear()

    root_logger.addHandler(
        handler
    )

    root_logger.setLevel(
        level
    )


def get_logger(
    name: str,
) -> logging.Logger:
    """
    Return a standard Python logger.

    Formatting and trace enrichment are handled centrally by
    JsonLogFormatter.
    """

    return logging.getLogger(
        name
    )


def log_event(
    logger: logging.Logger,
    level: int,
    message: str,
    **fields: Any,
) -> None:
    """
    Emit one structured application log event.

    Caller-provided fields are placed under structured_fields
    and later merged into the final JSON payload by
    JsonLogFormatter.

    Reserved observability fields such as trace_id, span_id,
    event_id, and correlation_id cannot be overridden here.
    """

    logger.log(
        level,
        message,
        extra={
            "structured_fields":
                fields
        },
    )