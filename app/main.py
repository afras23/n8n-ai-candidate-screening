"""
FastAPI application factory and ASGI entrypoint.

Registers middleware, routers, structured logging, and exception handlers.
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import health
from app.config import settings
from app.core.constants import API_V1_PREFIX
from app.core.database import engine
from app.core.exceptions import BaseAppError
from app.core.logging_config import (
    CorrelationIdMiddleware,
    configure_logging,
    get_correlation_id,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Configure logging at startup and release DB resources on shutdown."""
    configure_logging(settings.log_level)
    logger.info(
        "application_startup",
        extra={
            "app_env": settings.app_env,
            "app_version": settings.app_version,
        },
    )
    yield
    logger.info("application_shutdown", extra={})
    await engine.dispose()


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    application = FastAPI(
        title="n8n AI Candidate Screening",
        version=settings.app_version,
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    application.add_middleware(CorrelationIdMiddleware)
    if settings.cors_allow_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allow_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    _register_exception_handlers(application)
    application.include_router(health.router, prefix=API_V1_PREFIX)
    return application


def _register_exception_handlers(application: FastAPI) -> None:
    """Map domain errors and unexpected failures to JSON responses."""

    @application.exception_handler(BaseAppError)
    async def handle_app_error(_request: Request, exc: BaseAppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "status": "error",
                "error": {
                    "code": exc.error_code,
                    "message": exc.message,
                    "context": exc.context,
                },
                "metadata": {
                    "correlation_id": get_correlation_id(),
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            },
        )


app = create_app()
