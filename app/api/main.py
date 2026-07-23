"""
FastAPI application factory.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.health import router as health_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.results import router as results_router
from app.config import get_settings
from app.logging import configure_logging
from app.storage.database import close_db, init_db


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — startup and shutdown."""
    configure_logging()
    settings = get_settings()

    if settings.is_development:
        # Auto-create tables in development (use Alembic in production)
        await init_db()

    yield  # App is running

    await close_db()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Lead Intelligence & Email Discovery Engine",
        description=(
            "Enterprise-grade email discovery, validation, and business enrichment API. "
            "Fully deterministic — zero AI dependency."
        ),
        version="1.0.0",
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["*"],
    )

    # Routes
    app.include_router(health_router)
    app.include_router(jobs_router)
    app.include_router(results_router)

    return app


app = create_app()
