from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.api.routes.health import (
    router as health_router,
)
from services.api.routes.market import (
    router as market_router,
)
from services.api.routes.news import (
    router as news_router,
)
from services.api.routes.outbox import (
    router as outbox_router,
)
from services.api.routes.portfolio import (
    router as portfolio_router,
)
from services.api.routes.trading import (
    router as trading_router,
)
from services.api.routes.trading_simulation import (
    router as trading_simulation_router,
)
from services.api.routes.watchlist import (
    router as watchlist_router,
)


def get_cors_allowed_origins() -> list[str]:
    raw_origins = os.getenv(
        "CORS_ALLOWED_ORIGINS",
        (
            "http://127.0.0.1:5173,"
            "http://localhost:5173"
        ),
    )

    return [
        origin.strip()
        for origin in raw_origins.split(",")
        if origin.strip()
    ]


app = FastAPI(
    title="RealStock Enterprise API",
    version="0.3.0",
    description=(
        "Enterprise-grade real-time stock market data "
        "and risk monitoring platform."
    ),
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_allowed_origins(),
    allow_credentials=False,
    allow_methods=[
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "OPTIONS",
    ],
    allow_headers=[
        "Accept",
        "Authorization",
        "Content-Type",
        "X-User-ID",
    ],
)


ROUTERS = (
    health_router,
    portfolio_router,
    market_router,
    watchlist_router,
    outbox_router,
    news_router,
    trading_router,
    trading_simulation_router,
)

for api_router in ROUTERS:
    app.router.routes.extend(
        api_router.routes
    )
