"""
Health, readiness, and operational metrics endpoints.

Readiness executes a lightweight database check when a session is available.
"""

import logging
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe without external dependencies."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/health/ready")
async def readiness(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, object]:
    """Readiness probe including database connectivity."""
    checks: dict[str, str] = {}
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except SQLAlchemyError as exc:
        await db.rollback()
        logger.warning(
            "readiness_database_check_failed",
            extra={
                "error_type": type(exc).__name__,
            },
        )
        checks["database"] = "error"

    all_ok = all(status == "ok" for status in checks.values())
    return {
        "status": "ready" if all_ok else "degraded",
        "checks": checks,
        "timestamp": datetime.now(UTC).isoformat(),
    }


@router.get("/metrics")
async def metrics() -> dict[str, object]:
    """Operational metrics stub; populated in later phases."""
    return {
        "status": "stub",
        "processed_today": None,
        "daily_cost_usd": None,
    }
