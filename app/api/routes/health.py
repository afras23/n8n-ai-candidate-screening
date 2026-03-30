"""
Health, readiness, and operational metrics endpoints.

Readiness executes a lightweight database check when a session is available.
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db
from app.models.candidate import Candidate, ScreeningResult
from app.models.job import JobRequirement

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
async def metrics(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, object]:
    """Operational metrics for dashboarding and alerting."""
    since = datetime.now(UTC) - timedelta(days=1)

    candidates_today_stmt = (
        select(func.count()).select_from(Candidate).where(Candidate.created_at >= since)
    )
    shortlisted_stmt = (
        select(func.count())
        .select_from(ScreeningResult)
        .where(
            ScreeningResult.created_at >= since,
            ScreeningResult.recommendation == "shortlist",
        )
    )
    rejected_stmt = (
        select(func.count())
        .select_from(ScreeningResult)
        .where(
            ScreeningResult.created_at >= since,
            ScreeningResult.recommendation == "reject",
        )
    )
    review_stmt = (
        select(func.count())
        .select_from(ScreeningResult)
        .where(
            ScreeningResult.created_at >= since,
            ScreeningResult.recommendation == "review",
        )
    )
    avg_score_stmt = select(func.avg(ScreeningResult.overall_score)).where(
        ScreeningResult.created_at >= since
    )
    avg_latency_stmt = select(func.avg(ScreeningResult.latency_ms)).where(
        ScreeningResult.created_at >= since
    )
    cost_today_stmt = select(
        func.coalesce(func.sum(ScreeningResult.cost_usd), 0.0),
    ).where(ScreeningResult.created_at >= since)
    active_jobs_stmt = (
        select(func.count())
        .select_from(JobRequirement)
        .where(JobRequirement.is_active.is_(True))
    )

    candidates_screened_today = int(
        (await db.execute(candidates_today_stmt)).scalar_one()
    )
    shortlisted_today = int((await db.execute(shortlisted_stmt)).scalar_one())
    rejected_today = int((await db.execute(rejected_stmt)).scalar_one())
    review_today = int((await db.execute(review_stmt)).scalar_one())

    avg_score_raw = (await db.execute(avg_score_stmt)).scalar_one()
    avg_latency_raw = (await db.execute(avg_latency_stmt)).scalar_one()
    cost_today_raw = (await db.execute(cost_today_stmt)).scalar_one()
    active_jobs = int((await db.execute(active_jobs_stmt)).scalar_one())

    return {
        "candidates_screened_today": candidates_screened_today,
        "shortlisted_today": shortlisted_today,
        "rejected_today": rejected_today,
        "review_today": review_today,
        "avg_score": float(avg_score_raw) if avg_score_raw is not None else 0.0,
        "avg_processing_ms": (
            float(avg_latency_raw) if avg_latency_raw is not None else 0.0
        ),
        "cost_today_usd": float(cost_today_raw) if cost_today_raw is not None else 0.0,
        "cost_limit_usd": settings.max_daily_cost_usd,
        "active_jobs": active_jobs,
    }
