from __future__ import annotations

from fastapi import FastAPI

from libs.config import get_settings
from services.api.app.api.health import router as health_router


settings = get_settings()


app = FastAPI(
    title="RealStock Enterprise API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


app.include_router(health_router)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "environment": settings.app_env,
        "status": "running",
    }