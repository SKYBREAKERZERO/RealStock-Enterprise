from __future__ import annotations

import signal
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import services.outbox_dispatcher.main as outbox_main
from libs.database.repositories.outbox import (
    OutboxBacklogSnapshot,
)

pytestmark = pytest.mark.unit


def _settings() -> SimpleNamespace:
    """
    Build the minimum settings contract required by main().
    """

    return SimpleNamespace(
        log_level="INFO",
        app_env="local",
        outbox_batch_size=10,
        outbox_lease_seconds=60,
        outbox_poll_interval_seconds=1.0,
        outbox_error_backoff_seconds=5.0,
        outbox_event_bus_name="default",
        outbox_metrics_namespace="RealStock/Outbox",
        outbox_metrics_interval_seconds=30,
    )


def test_build_worker_id_uses_hostname(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        outbox_main.socket,
        "gethostname",
        lambda: "worker-123",
    )

    worker_id = (
        outbox_main.build_worker_id()
    )

    assert worker_id == "outbox-worker-123"


def test_build_worker_id_strips_hostname(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        outbox_main.socket,
        "gethostname",
        lambda: "  worker-123  ",
    )

    worker_id = (
        outbox_main.build_worker_id()
    )

    assert worker_id == "outbox-worker-123"


def test_build_worker_id_rejects_empty_hostname(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        outbox_main.socket,
        "gethostname",
        lambda: "   ",
    )

    with pytest.raises(
        RuntimeError,
        match=(
            "unable to determine "
            "outbox worker hostname"
        ),
    ):
        outbox_main.build_worker_id()


def test_backlog_snapshot_provider_uses_short_lived_session(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session = MagicMock(
        name="session",
    )

    context_manager = MagicMock(
        name="session_context_manager",
    )

    context_manager.__enter__.return_value = (
        session
    )

    context_manager.__exit__.return_value = (
        False
    )

    session_factory = MagicMock(
        name="session_factory",
        return_value=context_manager,
    )

    get_session_factory = MagicMock(
        name="get_session_factory",
        return_value=session_factory,
    )

    snapshot = OutboxBacklogSnapshot(
        pending_count=4,
        oldest_pending_at=None,
    )

    repository = MagicMock(
        name="repository",
    )

    repository.get_backlog_snapshot.return_value = (
        snapshot
    )

    repository_class = MagicMock(
        name="OutboxRepository",
        return_value=repository,
    )

    monkeypatch.setattr(
        outbox_main,
        "get_session_factory",
        get_session_factory,
    )

    monkeypatch.setattr(
        outbox_main,
        "OutboxRepository",
        repository_class,
    )

    provider = (
        outbox_main
        .build_backlog_snapshot_provider()
    )

    get_session_factory.assert_called_once_with()

    session_factory.assert_not_called()

    result = provider()

    session_factory.assert_called_once_with()

    repository_class.assert_called_once_with(
        session
    )

    repository.get_backlog_snapshot.assert_called_once_with()

    assert result is snapshot


def test_install_signal_handlers_requests_graceful_stop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = MagicMock(
        name="runner",
    )

    registered_handlers: dict[
        signal.Signals,
        object,
    ] = {}

    def register_signal(
        signum: signal.Signals,
        handler: object,
    ) -> None:
        registered_handlers[
            signum
        ] = handler

    monkeypatch.setattr(
        outbox_main.signal,
        "signal",
        register_signal,
    )

    outbox_main.install_signal_handlers(
        runner=runner,
    )

    assert (
        signal.SIGINT
        in registered_handlers
    )

    sigint_handler = (
        registered_handlers[
            signal.SIGINT
        ]
    )

    assert callable(
        sigint_handler
    )

    sigint_handler(
        signal.SIGINT,
        None,
    )

    runner.request_stop.assert_called_once_with()

    if hasattr(
        signal,
        "SIGTERM",
    ):
        assert (
            signal.SIGTERM
            in registered_handlers
        )


def test_main_composes_worker_and_runs_forever(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings()

    get_settings = MagicMock(
        name="get_settings",
        return_value=settings,
    )

    configure_logging = MagicMock(
        name="configure_logging",
    )

    build_worker_id = MagicMock(
        name="build_worker_id",
        return_value="outbox-test-worker",
    )

    session_factory = MagicMock(
        name="session_factory",
    )

    get_session_factory = MagicMock(
        name="get_session_factory",
        return_value=session_factory,
    )

    publisher = MagicMock(
        name="publisher",
    )

    publisher_class = MagicMock(
        name="EventBridgeOutboxPublisher",
        return_value=publisher,
    )

    dispatcher = MagicMock(
        name="dispatcher",
    )

    dispatcher_class = MagicMock(
        name="OutboxDispatcher",
        return_value=dispatcher,
    )

    metrics = MagicMock(
        name="metrics",
    )

    metrics_class = MagicMock(
        name="CloudWatchOutboxMetrics",
        return_value=metrics,
    )

    stop_event = MagicMock(
        name="stop_event",
    )

    event_class = MagicMock(
        name="Event",
        return_value=stop_event,
    )

    backlog_provider = MagicMock(
        name="backlog_provider",
    )

    build_backlog_provider = MagicMock(
        name="build_backlog_snapshot_provider",
        return_value=backlog_provider,
    )

    runner = MagicMock(
        name="runner",
    )

    runner_class = MagicMock(
        name="OutboxRunner",
        return_value=runner,
    )

    install_signal_handlers = MagicMock(
        name="install_signal_handlers",
    )

    monkeypatch.setattr(
        outbox_main,
        "get_settings",
        get_settings,
    )

    monkeypatch.setattr(
        outbox_main,
        "configure_logging",
        configure_logging,
    )

    monkeypatch.setattr(
        outbox_main,
        "build_worker_id",
        build_worker_id,
    )

    monkeypatch.setattr(
        outbox_main,
        "get_session_factory",
        get_session_factory,
    )

    monkeypatch.setattr(
        outbox_main,
        "EventBridgeOutboxPublisher",
        publisher_class,
    )

    monkeypatch.setattr(
        outbox_main,
        "OutboxDispatcher",
        dispatcher_class,
    )

    monkeypatch.setattr(
        outbox_main,
        "CloudWatchOutboxMetrics",
        metrics_class,
    )

    monkeypatch.setattr(
        outbox_main,
        "Event",
        event_class,
    )

    monkeypatch.setattr(
        outbox_main,
        "build_backlog_snapshot_provider",
        build_backlog_provider,
    )

    monkeypatch.setattr(
        outbox_main,
        "OutboxRunner",
        runner_class,
    )

    monkeypatch.setattr(
        outbox_main,
        "install_signal_handlers",
        install_signal_handlers,
    )

    result = outbox_main.main()

    assert result == 0

    get_settings.assert_called_once_with()

    configure_logging.assert_called_once_with(
        log_level="INFO",
    )

    build_worker_id.assert_called_once_with()

    get_session_factory.assert_called_once_with()

    publisher_class.assert_called_once_with(
        event_bus_name="default",
    )

    dispatcher_class.assert_called_once_with(
        session_factory=session_factory,
        publisher=publisher,
        worker_id="outbox-test-worker",
        batch_size=10,
        lease_seconds=60,
    )

    metrics_class.assert_called_once_with(
        namespace="RealStock/Outbox",
        environment="local",
    )

    event_class.assert_called_once_with()

    build_backlog_provider.assert_called_once_with()

    runner_class.assert_called_once_with(
        dispatcher=dispatcher,
        backlog_snapshot_provider=(
            backlog_provider
        ),
        metrics=metrics,
        poll_interval_seconds=1.0,
        error_backoff_seconds=5.0,
        metrics_interval_seconds=30,
        stop_event=stop_event,
    )

    install_signal_handlers.assert_called_once_with(
        runner=runner,
    )

    runner.run_forever.assert_called_once_with()


def test_main_returns_one_when_worker_runtime_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings()

    runner = MagicMock(
        name="runner",
    )

    runner.run_forever.side_effect = (
        RuntimeError(
            "worker failed"
        )
    )

    monkeypatch.setattr(
        outbox_main,
        "get_settings",
        MagicMock(
            return_value=settings,
        ),
    )

    monkeypatch.setattr(
        outbox_main,
        "configure_logging",
        MagicMock(),
    )

    monkeypatch.setattr(
        outbox_main,
        "build_worker_id",
        MagicMock(
            return_value="outbox-test-worker",
        ),
    )

    monkeypatch.setattr(
        outbox_main,
        "get_session_factory",
        MagicMock(
            return_value=MagicMock(),
        ),
    )

    monkeypatch.setattr(
        outbox_main,
        "EventBridgeOutboxPublisher",
        MagicMock(
            return_value=MagicMock(),
        ),
    )

    monkeypatch.setattr(
        outbox_main,
        "OutboxDispatcher",
        MagicMock(
            return_value=MagicMock(),
        ),
    )

    monkeypatch.setattr(
        outbox_main,
        "CloudWatchOutboxMetrics",
        MagicMock(
            return_value=MagicMock(),
        ),
    )

    monkeypatch.setattr(
        outbox_main,
        "Event",
        MagicMock(
            return_value=MagicMock(),
        ),
    )

    monkeypatch.setattr(
        outbox_main,
        "build_backlog_snapshot_provider",
        MagicMock(
            return_value=MagicMock(),
        ),
    )

    monkeypatch.setattr(
        outbox_main,
        "OutboxRunner",
        MagicMock(
            return_value=runner,
        ),
    )

    monkeypatch.setattr(
        outbox_main,
        "install_signal_handlers",
        MagicMock(),
    )

    logger_exception = MagicMock()

    monkeypatch.setattr(
        outbox_main.logger,
        "exception",
        logger_exception,
    )

    result = outbox_main.main()

    assert result == 1

    runner.run_forever.assert_called_once_with()

    logger_exception.assert_called_once()


def test_main_treats_keyboard_interrupt_as_clean_shutdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings()

    runner = MagicMock(
        name="runner",
    )

    runner.run_forever.side_effect = (
        KeyboardInterrupt()
    )

    monkeypatch.setattr(
        outbox_main,
        "get_settings",
        MagicMock(
            return_value=settings,
        ),
    )

    monkeypatch.setattr(
        outbox_main,
        "configure_logging",
        MagicMock(),
    )

    monkeypatch.setattr(
        outbox_main,
        "build_worker_id",
        MagicMock(
            return_value="outbox-test-worker",
        ),
    )

    monkeypatch.setattr(
        outbox_main,
        "get_session_factory",
        MagicMock(
            return_value=MagicMock(),
        ),
    )

    monkeypatch.setattr(
        outbox_main,
        "EventBridgeOutboxPublisher",
        MagicMock(
            return_value=MagicMock(),
        ),
    )

    monkeypatch.setattr(
        outbox_main,
        "OutboxDispatcher",
        MagicMock(
            return_value=MagicMock(),
        ),
    )

    monkeypatch.setattr(
        outbox_main,
        "CloudWatchOutboxMetrics",
        MagicMock(
            return_value=MagicMock(),
        ),
    )

    monkeypatch.setattr(
        outbox_main,
        "Event",
        MagicMock(
            return_value=MagicMock(),
        ),
    )

    monkeypatch.setattr(
        outbox_main,
        "build_backlog_snapshot_provider",
        MagicMock(
            return_value=MagicMock(),
        ),
    )

    monkeypatch.setattr(
        outbox_main,
        "OutboxRunner",
        MagicMock(
            return_value=runner,
        ),
    )

    monkeypatch.setattr(
        outbox_main,
        "install_signal_handlers",
        MagicMock(),
    )

    result = outbox_main.main()

    assert result == 0

    runner.run_forever.assert_called_once_with()