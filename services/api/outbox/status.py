from __future__ import annotations

from enum import StrEnum


class OutboxEventStatus(StrEnum):
    ALL = "all"
    PENDING = "pending"
    PUBLISHED = "published"
    FAILED = "failed"
