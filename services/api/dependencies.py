from __future__ import annotations

from collections.abc import Generator
from typing import Annotated

from fastapi import (
    Depends,
    Header,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from libs.cache import get_redis_client
from libs.config import get_settings
from libs.database import get_db_session
from libs.database.unit_of_work import (
    SqlAlchemyUnitOfWork,
)
from services.api.market_batch import (
    BatchMarketQuoteService,
)
from services.api.market_snapshot_cache import (
    MarketSnapshotCache,
)
from services.api.portfolio.service import (
    PortfolioService,
)
from services.api.portfolio.valuation import (
    PortfolioValuationService,
)
from services.api.portfolio.valuation_price import (
    BatchMarketValuationPriceSource,
)
from services.market_ingestor.providers.twelve_data import (
    TwelveDataMarketDataProvider,
)


def get_current_user_id(
    x_user_id: Annotated[
        str | None,
        Header(alias="X-User-Id"),
    ] = None,
) -> str:
    """
    Temporary local identity boundary.

    Day N:
        X-User-Id

    Production:
        Cognito JWT -> sub
    """

    if x_user_id is None:
        raise HTTPException(
            status_code=(
                status
                .HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "missing X-User-Id header"
            ),
        )

    user_id = (
        x_user_id
        .strip()
    )

    if not user_id:
        raise HTTPException(
            status_code=(
                status
                .HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "invalid X-User-Id header"
            ),
        )

    if len(user_id) > 128:
        raise HTTPException(
            status_code=(
                status
                .HTTP_401_UNAUTHORIZED
            ),
            detail=(
                "invalid X-User-Id header"
            ),
        )

    return user_id


def get_portfolio_service(
    session: Annotated[
        Session,
        Depends(get_db_session),
    ],
) -> PortfolioService:
    unit_of_work = (
        SqlAlchemyUnitOfWork(
            session
        )
    )

    return PortfolioService(
        unit_of_work
    )


def get_portfolio_valuation_service(
) -> Generator[
    PortfolioValuationService,
    None,
    None,
]:
    """
    Build the portfolio valuation runtime.

    mock mode:
        Preserve the legacy bid/ask MarketQuoteCache valuation
        path. This also keeps deterministic unit/integration
        tests compatible.

    twelve_data mode:
        Twelve Data OHLC snapshot
            -> Redis fresh/stale cache
            -> BatchMarketQuoteService
            -> explicit valuation price
            -> snapshot.close

    Twelve Data close is used explicitly as the valuation
    price. It is never converted into synthetic bid/ask data.
    """

    settings = get_settings()

    if (
        settings.market_data_provider
        != "twelve_data"
    ):
        yield (
            PortfolioValuationService()
        )

        return

    if (
        settings.twelve_data_api_key
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
        TwelveDataMarketDataProvider(
            api_key=(
                settings
                .twelve_data_api_key
            ),
        )
    )

    cache = (
        MarketSnapshotCache(
            get_redis_client(),
            fresh_ttl_seconds=(
                settings
                .market_quote_cache_ttl_seconds
            ),
            stale_ttl_seconds=(
                settings
                .market_quote_stale_ttl_seconds
            ),
        )
    )

    batch_service = (
        BatchMarketQuoteService(
            provider=provider,
            cache=cache,
        )
    )

    price_source = (
        BatchMarketValuationPriceSource(
            batch_service
        )
    )

    valuation_service = (
        PortfolioValuationService(
            price_source=(
                price_source
            ),
        )
    )

    try:
        yield valuation_service

    finally:
        provider.close()