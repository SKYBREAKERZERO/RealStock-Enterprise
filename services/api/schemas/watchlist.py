from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AddWatchlistItemRequest(
    BaseModel
):
    symbol: str = Field(
        min_length=1,
        max_length=20,
    )


class WatchlistItemResponse(
    BaseModel
):
    model_config = ConfigDict(
        from_attributes=True
    )

    watchlist_item_id: UUID
    symbol: str
    created_at: datetime


class WatchlistResponse(
    BaseModel
):
    items: list[
        WatchlistItemResponse
    ]

    count: int