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

        if record.exc_info:
            payload[
                "exception"
            ] = self.formatException(
                record.exc_info
            )

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
    return logging.getLogger(
        name
    )


def log_event(
    logger: logging.Logger,
    level: int,
    message: str,
    **fields: Any,
) -> None:
    logger.log(
        level,
        message,
        extra={
            "structured_fields":
                fields
        },
    )