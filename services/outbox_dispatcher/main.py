from __future__ import annotations

import logging
import signal
import socket
from threading import Event

from libs.config import get_settings
from libs.database import get_session_factory
from libs.database.repositories.outbox import (
    OutboxRepository,
)
from services.outbox_dispatcher.dispatcher import (
    OutboxDispatcher,
)
from services.outbox_dispatcher.metrics import (
    CloudWatchOutboxMetrics,
)
from services.outbox_dispatcher.publisher import (
    EventBridgeOutboxPublisher,
)
from services.outbox_dispatcher.runner import (
    OutboxRunner,
)

LOGGER_NAME = "realstock.outbox_dispatcher"

logger = logging.getLogger(
    LOGGER_NAME
)


def configure_logging(
    *,
    log_level: str,
) -> None:
    """
    Configure process-level logging for the outbox worker.
    """

    level = getattr(
        logging,
        log_level.upper(),
        logging.INFO,
    )

    logging.basicConfig(
        level=level,
        format=(
            "%(asctime)s "
            "%(levelname)s "
            "%(name)s "
            "%(message)s"
        ),
    )


def build_worker_id() -> str:
    """
    Build a stable-enough identifier for one worker process.

    ECS tasks receive distinct hostnames, which keeps worker lease
    ownership unique across concurrently running task replicas.
    """

    hostname = (
        socket.gethostname()
        .strip()
    )

    if not hostname:
        raise RuntimeError(
            "unable to determine outbox worker hostname"
        )

    return (
        f"outbox-{hostname}"
    )


def build_backlog_snapshot_provider():
    """
    Build the database-backed operational backlog reader.

    Every invocation receives its own short-lived SQLAlchemy
    session. The repository performs read-only work and never
    commits.
    """

    session_factory = (
        get_session_factory()
    )

    def get_backlog_snapshot():
        with session_factory() as session:
            repository = (
                OutboxRepository(
                    session
                )
            )

            return (
                repository
                .get_backlog_snapshot()
            )

    return get_backlog_snapshot


def install_signal_handlers(
    *,
    runner: OutboxRunner,
) -> None:
    """
    Install graceful shutdown handlers.

    Signal handlers only request shutdown. They do not terminate
    an in-progress dispatch operation.
    """

    def handle_signal(
        signum: int,
        _frame: object,
    ) -> None:
        logger.info(
            "outbox_shutdown_requested "
            "signal=%s",
            signum,
        )

        runner.request_stop()

    signal.signal(
        signal.SIGINT,
        handle_signal,
    )

    if hasattr(
        signal,
        "SIGTERM",
    ):
        signal.signal(
            signal.SIGTERM,
            handle_signal,
        )


def main() -> int:
    """
    Compose and run the production outbox dispatcher worker.
    """

    settings = get_settings()

    configure_logging(
        log_level=settings.log_level,
    )

    worker_id = build_worker_id()

    logger.info(
        "outbox_worker_bootstrapping "
        "worker_id=%s "
        "environment=%s "
        "batch_size=%s "
        "lease_seconds=%s "
        "poll_interval_seconds=%s "
        "event_bus=%s",
        worker_id,
        settings.app_env,
        settings.outbox_batch_size,
        settings.outbox_lease_seconds,
        settings.outbox_poll_interval_seconds,
        settings.outbox_event_bus_name,
    )

    try:
        session_factory = (
            get_session_factory()
        )

        publisher = (
            EventBridgeOutboxPublisher(
                event_bus_name=(
                    settings
                    .outbox_event_bus_name
                ),
            )
        )

        dispatcher = (
            OutboxDispatcher(
                session_factory=(
                    session_factory
                ),
                publisher=publisher,
                worker_id=worker_id,
                batch_size=(
                    settings
                    .outbox_batch_size
                ),
                lease_seconds=(
                    settings
                    .outbox_lease_seconds
                ),
            )
        )

        metrics = (
            CloudWatchOutboxMetrics(
                namespace=(
                    settings
                    .outbox_metrics_namespace
                ),
                environment=(
                    settings.app_env
                ),
            )
        )

        stop_event = Event()

        runner = (
            OutboxRunner(
                dispatcher=dispatcher,
                backlog_snapshot_provider=(
                    build_backlog_snapshot_provider()
                ),
                metrics=metrics,
                poll_interval_seconds=(
                    settings
                    .outbox_poll_interval_seconds
                ),
                error_backoff_seconds=(
                    settings
                    .outbox_error_backoff_seconds
                ),
                metrics_interval_seconds=(
                    settings
                    .outbox_metrics_interval_seconds
                ),
                stop_event=stop_event,
            )
        )

        install_signal_handlers(
            runner=runner,
        )

        logger.info(
            "outbox_worker_started "
            "worker_id=%s",
            worker_id,
        )

        runner.run_forever()

        logger.info(
            "outbox_worker_stopped "
            "worker_id=%s",
            worker_id,
        )

        return 0

    except KeyboardInterrupt:
        logger.info(
            "outbox_keyboard_interrupt "
            "worker_id=%s",
            worker_id,
        )

        return 0

    except Exception:
        logger.exception(
            "outbox_worker_failed "
            "worker_id=%s",
            worker_id,
        )

        return 1


if __name__ == "__main__":
    raise SystemExit(
        main()
    )