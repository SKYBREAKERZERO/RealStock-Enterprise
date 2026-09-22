from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class NewsItem(BaseModel):
    id: str
    published_at: datetime
    title: str
    summary: str
    source: str
    url: str | None = None


class NewsResponse(BaseModel):
    items: list[NewsItem]
    count: int
    cached: bool