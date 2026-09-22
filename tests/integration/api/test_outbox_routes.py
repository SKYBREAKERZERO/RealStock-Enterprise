from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from libs.database import get_session_factory
from libs.database.models.outbox import (
    OutboxEventModel,
)
from services.api.main import app

pytestmark = pytest.mark.integration

client = TestClient(app)

USER_HEADERS = {
    "X-User-ID": "api-outbox-user-001",
}

AGGREGATE_PREFIX = "api-outbox-test-"


def _cleanup() -> None:
    session_factory = get_session_factory()

    with session_factory() as session:
        session.execute(
            delete(OutboxEventModel).where(
                OutboxEventModel.aggregate_id.like(
                    f"{AGGREGATE_PREFIX}%"
                )
            )
        )
        session.commit()


@pytest.fixture(autouse=True)
def cleanup_test_events():
    _cleanup()
    yield
    _cleanup()


def _insert_event(
    *,
    suffix: str,
    published: bool = False,
    failed: bool = False,
) -> str:
    session_factory = get_session_factory()

    event_id = uuid4()
    aggregate_id = (
        f"{AGGREGATE_PREFIX}{suffix}"
    )
    now = datetime.now(UTC)

    with session_factory() as session:
        session.add(
            OutboxEventModel(
                event_id=event_id,
                aggregate_type="portfolio",
                aggregate_id=aggregate_id,
                event_type=(
                    "portfolio.position.updated"
                ),
                schema_version=1,
                source="realstock-api",
                correlation_id=uuid4(),
                causation_id=None,
                trace_context=None,
                payload={
                    "aggregate_id": aggregate_id,
                },
                occurred_at=now,
                created_at=now,
                published_at=(
                    now
                    if published
                    else None
                ),
                attempt_count=(
                    1
                    if failed
                    else 0
                ),
                next_attempt_at=now,
                last_error=(
                    "test publish failure"
                    if failed
                    else None
                ),
                locked_until=None,
                locked_by=None,
            )
        )
        session.commit()

    return str(event_id)


def test_outbox_events_requires_identity() -> None:
    response = client.get(
        "/api/v1/outbox/events"
    )

    assert response.status_code == 401


def test_list_outbox_events_filters_status() -> None:
    pending_id = _insert_event(
        suffix="pending",
    )
    published_id = _insert_event(
        suffix="published",
        published=True,
    )
    failed_id = _insert_event(
        suffix="failed",
        failed=True,
    )

    pending_response = client.get(
        "/api/v1/outbox/events",
        headers=USER_HEADERS,
        params={
            "status": "pending",
            "aggregate_id": (
                f"{AGGREGATE_PREFIX}pending"
            ),
        },
    )

    assert pending_response.status_code == 200

    pending_payload = pending_response.json()

    assert pending_payload["count"] == 1
    assert (
        pending_payload["items"][0]["event_id"]
        == pending_id
    )
    assert (
        pending_payload["items"][0]["status"]
        == "pending"
    )

    published_response = client.get(
        "/api/v1/outbox/events",
        headers=USER_HEADERS,
        params={
            "status": "published",
            "aggregate_id": (
                f"{AGGREGATE_PREFIX}published"
            ),
        },
    )

    assert published_response.status_code == 200

    published_payload = (
        published_response.json()
    )

    assert published_payload["count"] == 1
    assert (
        published_payload["items"][0]["event_id"]
        == published_id
    )
    assert (
        published_payload["items"][0]["status"]
        == "published"
    )

    failed_response = client.get(
        "/api/v1/outbox/events",
        headers=USER_HEADERS,
        params={
            "status": "failed",
            "aggregate_id": (
                f"{AGGREGATE_PREFIX}failed"
            ),
        },
    )

    assert failed_response.status_code == 200

    failed_payload = failed_response.json()

    assert failed_payload["count"] == 1
    assert (
        failed_payload["items"][0]["event_id"]
        == failed_id
    )
    assert (
        failed_payload["items"][0]["status"]
        == "failed"
    )


def test_outbox_events_honors_limit() -> None:
    for index in range(3):
        _insert_event(
            suffix=f"limit-{index}",
        )

    response = client.get(
        "/api/v1/outbox/events",
        headers=USER_HEADERS,
        params={
            "limit": 2,
            "event_type": (
                "portfolio.position.updated"
            ),
        },
    )

    assert response.status_code == 200
    assert response.json()["count"] == 2


def test_outbox_summary_has_operational_counts() -> None:
    _insert_event(
        suffix="summary-pending",
    )
    _insert_event(
        suffix="summary-published",
        published=True,
    )
    _insert_event(
        suffix="summary-failed",
        failed=True,
    )

    response = client.get(
        "/api/v1/outbox/summary",
        headers=USER_HEADERS,
    )

    assert response.status_code == 200

    payload = response.json()

    assert payload["total_count"] >= 3
    assert payload["pending_count"] >= 1
    assert payload["published_count"] >= 1
    assert payload["failed_count"] >= 1
    assert payload["unpublished_count"] >= 2
