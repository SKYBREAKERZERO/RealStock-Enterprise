from fastapi import FastAPI

from services.api.routes.health import (
    router as health_router,
)
from services.api.routes.portfolio import (
    router as portfolio_router,
)

app = FastAPI(
    title="RealStock Enterprise API",
    version="0.2.0",
    description=(
        "Enterprise-grade real-time stock market data "
        "and risk monitoring platform."
    ),
)


app.include_router(
    health_router
)

app.include_router(
    portfolio_router
)