from __future__ import annotations

import os

from collections.abc import Generator
from typing import Annotated

from fastapi import (
    Depends,
    Header,
    HTTPException,
    status,
)
from sqlalchemy.orm import Session

from libs.cache import (
    MarketQuoteCache,
    get_redis_client,
)
from libs.config import get_settings
from libs.database import get_db_session
from libs.database.unit_of_work import (
    SqlAlchemyUnitOfWork,
)
from libs.trading.paper_broker import PaperBroker
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
from services.trading.cached_quote_provider import (
    CachedMarketQuoteProvider,
)
from services.trading.paper_trading_service import (
    PaperTradingService,
)
from services.trading.persistent_paper_trading_service import (
    PersistentPaperTradingService,
)
from services.trading.quote_service import QuoteService
from services.trading.trading_portfolio_service import (
    TradingPortfolioService,
)
from services.trading.trading_query_service import (
    TradingQueryService,
)
from services.trading.trading_valuation_price import (
    BatchTradingValuationPriceSource,
    CachedTradingValuationPriceSource,
)
from services.trading.trading_write_service import (
    TradingWriteService,
)


from libs.cache import MarketQuoteCache
from libs.trading.paper_broker import PaperBroker
from services.trading.cached_quote_provider import (
    CachedMarketQuoteProvider,
)
from services.trading.paper_trading_service import (
    PaperTradingService,
)
from services.trading.persistent_paper_trading_service import (
    PersistentPaperTradingService,
)
from services.trading.quote_service import QuoteService
from services.trading.trading_write_service import TradingWriteService


from services.trading.trading_account_service import (
    TradingAccountService,
)


from services.trading.alpaca_quote_provider import (
    AlpacaCachedTradingQuoteProvider,
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


def get_trading_query_service(
    session: Annotated[
        Session,
        Depends(get_db_session),
    ],
) -> TradingQueryService:
    unit_of_work = (
        SqlAlchemyUnitOfWork(
            session
        )
    )

    return TradingQueryService(
        unit_of_work=unit_of_work,
    )


def get_persistent_paper_trading_service(
    session: Annotated[
        Session,
        Depends(get_db_session),
    ],
) -> PersistentPaperTradingService:
    """
    Build the canonical paper-trading write runtime.

    Trade execution always consumes a real bid/ask MarketQuote from
    MarketQuoteCache through CachedMarketQuoteProvider.

    BUY executes at ask and SELL executes at bid in PaperBroker.
    OHLC snapshot close is never converted into trading bid/ask.
    """

    quote_provider = (
        CachedMarketQuoteProvider(
            cache=MarketQuoteCache(),
        )
    )

    quote_service = QuoteService(
        provider=quote_provider,
    )

    trading_service = (
        PaperTradingService(
            quote_service=quote_service,
            broker=PaperBroker(),
        )
    )

    return PersistentPaperTradingService(
        trading_service=trading_service,
        unit_of_work=(
            SqlAlchemyUnitOfWork(
                session
            )
        ),
    )


def get_trading_write_service(
    session: Annotated[
        Session,
        Depends(get_db_session),
    ],
) -> TradingWriteService:
    quote_cache = MarketQuoteCache()

    alpaca_key_id = os.getenv(
        "ALPACA_API_KEY_ID",
        "",
    ).strip()

    alpaca_secret_key = os.getenv(
        "ALPACA_API_SECRET_KEY",
        "",
    ).strip()

    if alpaca_key_id and alpaca_secret_key:
        quote_provider = (
            AlpacaCachedTradingQuoteProvider(
                cache=quote_cache,
                api_key_id=alpaca_key_id,
                api_secret_key=alpaca_secret_key,
                feed=os.getenv(
                    "ALPACA_DATA_FEED",
                    "iex",
                ),
                base_url=os.getenv(
                    "ALPACA_MARKET_DATA_BASE_URL",
                    "https://data.alpaca.markets",
                ),
                timeout_seconds=float(
                    os.getenv(
                        "ALPACA_QUOTE_TIMEOUT_SECONDS",
                        "5",
                    )
                ),
            )
        )
    else:
        quote_provider = (
            CachedMarketQuoteProvider(
                cache=quote_cache,
            )
        )

    trading_service = PaperTradingService(
        quote_service=QuoteService(
            provider=quote_provider,
        ),
        broker=PaperBroker(),
    )

    return TradingWriteService(
        query_service=TradingQueryService(
            unit_of_work=SqlAlchemyUnitOfWork(
                session
            ),
        ),
        persistent_service=(
            PersistentPaperTradingService(
                trading_service=trading_service,
                unit_of_work=SqlAlchemyUnitOfWork(
                    session
                ),
            )
        ),
    )



def get_trading_portfolio_service(
    session: Annotated[
        Session,
        Depends(get_db_session),
    ],
) -> Generator[
    TradingPortfolioService,
    None,
    None,
]:
    """
    Build the paper-trading valuation runtime.

    Legacy/local mode:
        MarketQuoteCache
        -> real bid/ask quote
        -> midpoint valuation price

    Twelve Data mode:
        Twelve Data OHLC snapshot
        -> Redis fresh/stale cache
        -> BatchMarketValuationPriceSource
        -> snapshot.close valuation price

    Neither path fabricates bid/ask semantics from OHLC close.
    """

    unit_of_work = (
        SqlAlchemyUnitOfWork(
            session
        )
    )

    settings = get_settings()

    if (
        settings.market_data_provider
        != "twelve_data"
    ):
        yield TradingPortfolioService(
            unit_of_work=unit_of_work,
            price_source=(
                CachedTradingValuationPriceSource(
                    quote_cache=(
                        MarketQuoteCache()
                    ),
                )
            ),
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

    portfolio_price_source = (
        BatchMarketValuationPriceSource(
            batch_service
        )
    )

    trading_price_source = (
        BatchTradingValuationPriceSource(
            price_source=(
                portfolio_price_source
            ),
        )
    )

    service = TradingPortfolioService(
        unit_of_work=unit_of_work,
        price_source=trading_price_source,
    )

    try:
        yield service

    finally:
        provider.close()


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


def get_trading_account_service(
    session: Annotated[
        Session,
        Depends(get_db_session),
    ],
) -> TradingAccountService:
    return TradingAccountService(
        unit_of_work=SqlAlchemyUnitOfWork(
            session
        ),
    )
