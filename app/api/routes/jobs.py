"""Job requirement HTTP routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.common import SuccessEnvelope
from app.api.schemas.jobs import JobCreateRequest, JobResponse
from app.dependencies import get_db
from app.models.job import JobRequirement
from app.repositories.job_repo import JobRepository

router = APIRouter(tags=["jobs"])


@router.get("/jobs")
async def list_jobs(db: Annotated[AsyncSession, Depends(get_db)]) -> JSONResponse:
    repo = JobRepository(db)
    jobs = await repo.list_active()
    payload = [
        JobResponse(
            id=row.id,
            title=row.title,
            description=row.description,
            requirements_json=row.requirements_json,
            scoring_rubric_json=row.scoring_rubric_json,
            is_active=row.is_active,
            created_at=row.created_at.isoformat(),
        )
        for row in jobs
    ]
    return JSONResponse(
        status_code=200,
        content=SuccessEnvelope(data=payload).model_dump(mode="json"),
    )


@router.post("/jobs")
async def create_job(
    request: JobCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JSONResponse:
    job = JobRequirement(
        title=request.title,
        description=request.description,
        requirements_json=request.requirements_json,
        scoring_rubric_json=request.scoring_rubric_json,
        is_active=True,
    )
    db.add(job)
    await db.flush()
    response = JobResponse(
        id=job.id,
        title=job.title,
        description=job.description,
        requirements_json=job.requirements_json,
        scoring_rubric_json=job.scoring_rubric_json,
        is_active=job.is_active,
        created_at=job.created_at.isoformat(),
    )
    return JSONResponse(
        status_code=200,
        content=SuccessEnvelope(data=response).model_dump(mode="json"),
    )
