from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, Mock, patch
from uuid import UUID

import pytest
from services.outbox_dispatcher.dispatcher import (
    OutboxDispatcher,
)

from libs.database.repositories.outbox import (
    ClaimedOutboxEvent,
)
from services.outbox_dispatcher.publisher import (
    EventBridgeOutboxPublisher,
    EventBridgePublishResult,
)

pytestmark = pytest.mark.unit


TEST_NOW = datetime(
    2026,
    9,
    19,
    4,
    0,
    tzinfo=UTC,
)


def _claimed_event(
    *,
    event_id: str = (
        "22222222-2222-2222-2222-222222222222"
    ),
    attempt_count: int = 0,
) -> ClaimedOutboxEvent:
    return ClaimedOutboxEvent(
        id=UUID(
            "11111111-1111-1111-1111-111111111111"
        ),
        event_id=UUID(
            event_id
        ),
        aggregate_type="portfolio",
        aggregate_id=(
            "33333333-3333-3333-3333-333333333333"
        ),
        event_type="portfolio.created",
        schema_version=1,
        source="portfolio-api",
        correlation_id=UUID(
            "44444444-4444-4444-4444-444444444444"
        ),
        causation_id=None,
        trace_context={
            "traceparent": (
                "00-"
                "0123456789abcdef0123456789abcdef-"
                "0123456789abcdef-01"
            )
        },
        payload={
            "portfolio_id": (
                "33333333-3333-3333-3333-333333333333"
            ),
            "user_id": "user-001",
            "name": "Long Term Portfolio",
            "currency": "USD",
        },
        occurred_at=(
            TEST_NOW
            - timedelta(
                minutes=1
            )
        ),
        attempt_count=attempt_count,
        locked_by="worker-001",
        locked_until=(
            TEST_NOW
            + timedelta(
                seconds=60
            )
        ),
    )


def _session() -> MagicMock:
    session = MagicMock()

    session.__enter__.return_value = (
        session
    )

    session.__exit__.return_value = (
        False
    )

    return session


def _publisher() -> Mock:
    return Mock(
        spec=EventBridgeOutboxPublisher
    )


def test_dispatch_once_returns_empty_result_when_nothing_is_due() -> None:
    claim_session = _session()

    session_factory = Mock(
        return_value=claim_session
    )

    publisher = _publisher()

    claim_repository = Mock()

    claim_repository.claim_pending.return_value = []

    with patch(
        (
            "services.outbox_dispatcher."
            "dispatcher.OutboxRepository"
        ),
        return_value=claim_repository,
    ):
        dispatcher = OutboxDispatcher(
            session_factory=session_factory,
            publisher=publisher,
            worker_id="worker-001",
            batch_size=10,
            lease_seconds=60,
        )

        result = dispatcher.dispatch_once(
            now=TEST_NOW
        )

    assert result.claimed == 0
    assert result.published == 0
    assert result.failed == 0

    claim_repository.claim_pending.assert_called_once_with(
        worker_id="worker-001",
        batch_size=10,
        lease_seconds=60,
        now=TEST_NOW,
    )

    claim_session.commit.assert_called_once()

    publisher.publish.assert_not_called()


def test_dispatch_once_publishes_claimed_event() -> None:
    event = _claimed_event()

    claim_session = _session()
    ack_session = _session()

    session_factory = Mock(
        side_effect=[
            claim_session,
            ack_session,
        ]
    )

    publisher = _publisher()

    publisher.publish.return_value = (
        EventBridgePublishResult(
            event_id="aws-event-001"
        )
    )

    claim_repository = Mock()
    ack_repository = Mock()

    claim_repository.claim_pending.return_value = [
        event
    ]

    ack_repository.mark_published.return_value = (
        True
    )

    with patch(
        (
            "services.outbox_dispatcher."
            "dispatcher.OutboxRepository"
        ),
        side_effect=[
            claim_repository,
            ack_repository,
        ],
    ):
        dispatcher = OutboxDispatcher(
            session_factory=session_factory,
            publisher=publisher,
            worker_id="worker-001",
            batch_size=10,
            lease_seconds=60,
        )

        result = dispatcher.dispatch_once(
            now=TEST_NOW
        )

    assert result.claimed == 1
    assert result.published == 1
    assert result.failed == 0

    publisher.publish.assert_called_once_with(
        event
    )

    ack_repository.mark_published.assert_called_once_with(
        event_id=event.event_id,
        worker_id="worker-001",
        published_at=TEST_NOW,
    )

    claim_session.commit.assert_called_once()
    ack_session.commit.assert_called_once()


def test_claim_transaction_commits_before_network_publish() -> None:
    event = _claimed_event()

    operations: list[str] = []

    claim_session = _session()
    ack_session = _session()

    session_factory = Mock(
        side_effect=[
            claim_session,
            ack_session,
        ]
    )

    claim_repository = Mock()
    ack_repository = Mock()

    publisher = _publisher()

    def claim_events(
        **_: object,
    ) -> list[ClaimedOutboxEvent]:
        operations.append(
            "claim"
        )

        return [
            event
        ]

    def commit_claim() -> None:
        operations.append(
            "claim_commit"
        )

    def publish_event(
        _: ClaimedOutboxEvent,
    ) -> EventBridgePublishResult:
        operations.append(
            "publish"
        )

        return EventBridgePublishResult(
            event_id="aws-event-001"
        )

    def mark_published(
        **_: object,
    ) -> bool:
        operations.append(
            "mark_published"
        )

        return True

    def commit_ack() -> None:
        operations.append(
            "ack_commit"
        )

    claim_repository.claim_pending.side_effect = (
        claim_events
    )

    claim_session.commit.side_effect = (
        commit_claim
    )

    publisher.publish.side_effect = (
        publish_event
    )

    ack_repository.mark_published.side_effect = (
        mark_published
    )

    ack_session.commit.side_effect = (
        commit_ack
    )

    with patch(
        (
            "services.outbox_dispatcher."
            "dispatcher.OutboxRepository"
        ),
        side_effect=[
            claim_repository,
            ack_repository,
        ],
    ):
        dispatcher = OutboxDispatcher(
            session_factory=session_factory,
            publisher=publisher,
            worker_id="worker-001",
            batch_size=10,
            lease_seconds=60,
        )

        dispatcher.dispatch_once(
            now=TEST_NOW
        )

    assert operations == [
        "claim",
        "claim_commit",
        "publish",
        "mark_published",
        "ack_commit",
    ]


def test_publish_failure_marks_event_for_retry() -> None:
    event = _claimed_event(
        attempt_count=0
    )

    claim_session = _session()
    failure_session = _session()

    session_factory = Mock(
        side_effect=[
            claim_session,
            failure_session,
        ]
    )

    publisher = _publisher()

    publisher.publish.side_effect = (
        RuntimeError(
            "eventbridge unavailable"
        )
    )

    claim_repository = Mock()
    failure_repository = Mock()

    claim_repository.claim_pending.return_value = [
        event
    ]

    failure_repository.mark_failed.return_value = (
        True
    )

    with patch(
        (
            "services.outbox_dispatcher."
            "dispatcher.OutboxRepository"
        ),
        side_effect=[
            claim_repository,
            failure_repository,
        ],
    ):
        dispatcher = OutboxDispatcher(
            session_factory=session_factory,
            publisher=publisher,
            worker_id="worker-001",
            batch_size=10,
            lease_seconds=60,
        )

        result = dispatcher.dispatch_once(
            now=TEST_NOW
        )

    assert result.claimed == 1
    assert result.published == 0
    assert result.failed == 1

    failure_repository.mark_failed.assert_called_once_with(
        event_id=event.event_id,
        worker_id="worker-001",
        error="eventbridge unavailable",
        next_attempt_at=(
            TEST_NOW
            + timedelta(
                seconds=5
            )
        ),
    )

    failure_session.commit.assert_called_once()


def test_retry_delay_increases_with_attempt_count() -> None:
    event = _claimed_event(
        attempt_count=2
    )

    claim_session = _session()
    failure_session = _session()

    session_factory = Mock(
        side_effect=[
            claim_session,
            failure_session,
        ]
    )

    publisher = _publisher()

    publisher.publish.side_effect = (
        RuntimeError(
            "temporary failure"
        )
    )

    claim_repository = Mock()
    failure_repository = Mock()

    claim_repository.claim_pending.return_value = [
        event
    ]

    failure_repository.mark_failed.return_value = (
        True
    )

    with patch(
        (
            "services.outbox_dispatcher."
            "dispatcher.OutboxRepository"
        ),
        side_effect=[
            claim_repository,
            failure_repository,
        ],
    ):
        dispatcher = OutboxDispatcher(
            session_factory=session_factory,
            publisher=publisher,
            worker_id="worker-001",
            batch_size=10,
            lease_seconds=60,
        )

        dispatcher.dispatch_once(
            now=TEST_NOW
        )

    failure_repository.mark_failed.assert_called_once_with(
        event_id=event.event_id,
        worker_id="worker-001",
        error="temporary failure",
        next_attempt_at=(
            TEST_NOW
            + timedelta(
                seconds=120
            )
        ),
    )


def test_retry_delay_is_capped() -> None:
    event = _claimed_event(
        attempt_count=99
    )

    claim_session = _session()
    failure_session = _session()

    session_factory = Mock(
        side_effect=[
            claim_session,
            failure_session,
        ]
    )

    publisher = _publisher()

    publisher.publish.side_effect = (
        RuntimeError(
            "temporary failure"
        )
    )

    claim_repository = Mock()
    failure_repository = Mock()

    claim_repository.claim_pending.return_value = [
        event
    ]

    failure_repository.mark_failed.return_value = (
        True
    )

    with patch(
        (
            "services.outbox_dispatcher."
            "dispatcher.OutboxRepository"
        ),
        side_effect=[
            claim_repository,
            failure_repository,
        ],
    ):
        dispatcher = OutboxDispatcher(
            session_factory=session_factory,
            publisher=publisher,
            worker_id="worker-001",
            batch_size=10,
            lease_seconds=60,
        )

        dispatcher.dispatch_once(
            now=TEST_NOW
        )

    failure_repository.mark_failed.assert_called_once_with(
        event_id=event.event_id,
        worker_id="worker-001",
        error="temporary failure",
        next_attempt_at=(
            TEST_NOW
            + timedelta(
                seconds=600
            )
        ),
    )


def test_dispatch_continues_after_one_event_fails() -> None:
    first_event = _claimed_event(
        event_id=(
            "22222222-2222-2222-2222-222222222222"
        ),
    )

    second_event = _claimed_event(
        event_id=(
            "55555555-5555-5555-5555-555555555555"
        ),
    )

    third_event = _claimed_event(
        event_id=(
            "66666666-6666-6666-6666-666666666666"
        ),
    )

    claim_session = _session()
    success_one_session = _session()
    failure_session = _session()
    success_two_session = _session()

    session_factory = Mock(
        side_effect=[
            claim_session,
            success_one_session,
            failure_session,
            success_two_session,
        ]
    )

    publisher = _publisher()

    publisher.publish.side_effect = [
        EventBridgePublishResult(
            event_id="aws-event-001"
        ),
        RuntimeError(
            "temporary failure"
        ),
        EventBridgePublishResult(
            event_id="aws-event-003"
        ),
    ]

    claim_repository = Mock()
    success_one_repository = Mock()
    failure_repository = Mock()
    success_two_repository = Mock()

    claim_repository.claim_pending.return_value = [
        first_event,
        second_event,
        third_event,
    ]

    success_one_repository.mark_published.return_value = (
        True
    )

    failure_repository.mark_failed.return_value = (
        True
    )

    success_two_repository.mark_published.return_value = (
        True
    )

    with patch(
        (
            "services.outbox_dispatcher."
            "dispatcher.OutboxRepository"
        ),
        side_effect=[
            claim_repository,
            success_one_repository,
            failure_repository,
            success_two_repository,
        ],
    ):
        dispatcher = OutboxDispatcher(
            session_factory=session_factory,
            publisher=publisher,
            worker_id="worker-001",
            batch_size=10,
            lease_seconds=60,
        )

        result = dispatcher.dispatch_once(
            now=TEST_NOW
        )

    assert result.claimed == 3
    assert result.published == 2
    assert result.failed == 1

    assert publisher.publish.call_count == 3

    success_one_repository.mark_published.assert_called_once_with(
        event_id=first_event.event_id,
        worker_id="worker-001",
        published_at=TEST_NOW,
    )

    failure_repository.mark_failed.assert_called_once_with(
        event_id=second_event.event_id,
        worker_id="worker-001",
        error="temporary failure",
        next_attempt_at=(
            TEST_NOW
            + timedelta(
                seconds=5
            )
        ),
    )

    success_two_repository.mark_published.assert_called_once_with(
        event_id=third_event.event_id,
        worker_id="worker-001",
        published_at=TEST_NOW,
    )


@pytest.mark.parametrize(
    "worker_id",
    [
        "",
        " ",
        "   ",
    ],
)
def test_worker_id_must_not_be_empty(
    worker_id: str,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "worker_id must not be empty"
        ),
    ):
        OutboxDispatcher(
            session_factory=Mock(),
            publisher=_publisher(),
            worker_id=worker_id,
        )


@pytest.mark.parametrize(
    "batch_size",
    [
        0,
        -1,
    ],
)
def test_batch_size_must_be_positive(
    batch_size: int,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "batch_size must be greater than zero"
        ),
    ):
        OutboxDispatcher(
            session_factory=Mock(),
            publisher=_publisher(),
            worker_id="worker-001",
            batch_size=batch_size,
        )


@pytest.mark.parametrize(
    "lease_seconds",
    [
        0,
        -1,
    ],
)
def test_lease_seconds_must_be_positive(
    lease_seconds: int,
) -> None:
    with pytest.raises(
        ValueError,
        match=(
            "lease_seconds must be greater than zero"
        ),
    ):
        OutboxDispatcher(
            session_factory=Mock(),
            publisher=_publisher(),
            worker_id="worker-001",
            lease_seconds=lease_seconds,
        )


def test_dispatch_rejects_naive_now() -> None:
    dispatcher = OutboxDispatcher(
        session_factory=Mock(),
        publisher=_publisher(),
        worker_id="worker-001",
    )

    naive_now = datetime(
        2026,
        9,
        19,
        4,
        0,
    )

    with pytest.raises(
        ValueError,
        match="timezone-aware",
    ):
        dispatcher.dispatch_once(
            now=naive_now
        )