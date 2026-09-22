from __future__ import annotations

from collections.abc import Generator
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)

from libs.cache import get_redis_client
from libs.config import get_settings
from services.api.news_cache import NewsCache
from services.api.news_provider import (
    NewsProviderError,
    TwelveDataNewsProvider,
)
from services.api.news_service import NewsService
from services.api.routes.watchlist import (
    get_current_user_id,
    get_watchlist_service,
)
from services.api.schemas.news import NewsResponse
from services.api.watchlist import WatchlistService

router = APIRouter(
    prefix="/api/v1/news",
    tags=["news"],
)


_NEWS_FRESH_TTL_SECONDS = 300

_NEWS_STALE_TTL_SECONDS = 1800


def get_news_provider(
) -> Generator[
    TwelveDataNewsProvider,
    None,
    None,
]:
    settings = get_settings()

    if (
        settings
        .twelve_data_api_key
        is None
    ):
        raise HTTPException(
            status_code=(
                status
                .HTTP_503_SERVICE_UNAVAILABLE
            ),
            detail=(
                "Twelve Data API key "
                "is not configured"
            ),
        )

    provider = (
        TwelveDataNewsProvider(
            api_key=(
                settings
                .twelve_data_api_key
            ),
        )
    )

    try:
        yield provider

    finally:
        provider.close()


def get_news_cache(
) -> NewsCache:
    return NewsCache(
        get_redis_client(),
        fresh_ttl_seconds=(
            _NEWS_FRESH_TTL_SECONDS
        ),
        stale_ttl_seconds=(
            _NEWS_STALE_TTL_SECONDS
        ),
    )


def get_news_service(
    provider: Annotated[
        TwelveDataNewsProvider,
        Depends(
            get_news_provider
        ),
    ],
    cache: Annotated[
        NewsCache,
        Depends(
            get_news_cache
        ),
    ],
) -> NewsService:
    return NewsService(
        provider=provider,
        cache=cache,
    )


@router.get(
    "",
    response_model=NewsResponse,
)
def read_latest_news(
    user_id: Annotated[
        str,
        Depends(
            get_current_user_id
        ),
    ],
    watchlist_service: Annotated[
        WatchlistService,
        Depends(
            get_watchlist_service
        ),
    ],
    news_service: Annotated[
        NewsService,
        Depends(
            get_news_service
        ),
    ],
    limit: Annotated[
        int,
        Query(
            ge=1,
            le=20,
        ),
    ] = 20,
) -> NewsResponse:
    watchlist_items = (
        watchlist_service
        .list_items(
            user_id=user_id,
        )
    )

    symbols = [
        item.symbol
        for item
        in watchlist_items
    ]

    try:
        return (
            news_service
            .get_latest(
                symbols=symbols,
                limit=limit,
            )
        )

    except NewsProviderError as exc:
        raise HTTPException(
            status_code=(
                status
                .HTTP_502_BAD_GATEWAY
            ),
            detail=(
                "Live news provider "
                "is unavailable."
            ),
        ) from exc