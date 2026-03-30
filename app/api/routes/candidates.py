"""Candidate HTTP routes."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.candidates import (
    CandidateDetailResponse,
    CandidateListResponse,
    CandidateSummary,
    ScreeningResultDetail,
)
from app.api.schemas.common import ErrorBody, ErrorEnvelope, SuccessEnvelope
from app.dependencies import get_db
from app.repositories.candidate_repo import CandidateRepository
from app.repositories.screening_read_repo import ScreeningReadRepository

router = APIRouter(tags=["candidates"])


def _parse_datetime(value: str | None) -> datetime | None:
    if value is None or value.strip() == "":
        return None
    return datetime.fromisoformat(value)


def get_candidate_repo(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CandidateRepository:
    """Dependency provider for CandidateRepository."""

    return CandidateRepository(db)


def get_screening_read_repo(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ScreeningReadRepository:
    """Dependency provider for ScreeningReadRepository."""

    return ScreeningReadRepository(db)


@router.get("/candidates")
async def list_candidates(
    db: Annotated[AsyncSession, Depends(get_db)],
    candidate_repo: Annotated[CandidateRepository, Depends(get_candidate_repo)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 20,
    job_id: Annotated[uuid.UUID | None, Query()] = None,
    recommendation: Annotated[str | None, Query()] = None,
    created_from: Annotated[str | None, Query()] = None,
    created_to: Annotated[str | None, Query()] = None,
) -> JSONResponse:
    try:
        created_from_dt = _parse_datetime(created_from)
        created_to_dt = _parse_datetime(created_to)
    except ValueError:
        return JSONResponse(
            status_code=422,
            content=ErrorEnvelope(
                error=ErrorBody(
                    code="VALIDATION_ERROR",
                    message="Invalid date range format (use ISO-8601)",
                ),
            ).model_dump(),
        )

    offset = (page - 1) * page_size
    candidates = await candidate_repo.list_candidates(
        offset=offset,
        limit=page_size,
        job_id=job_id,
        recommendation=recommendation,
        created_from=created_from_dt,
        created_to=created_to_dt,
    )
    total = await candidate_repo.count_candidates(
        job_id=job_id,
        recommendation=recommendation,
    )
    response = CandidateListResponse(
        items=[
            CandidateSummary(
                id=row.id,
                name=row.name,
                email=row.email,
                created_at=row.created_at.isoformat(),
            )
            for row in candidates
        ],
        page=page,
        page_size=page_size,
        total=total,
    )
    return JSONResponse(
        status_code=200,
        content=SuccessEnvelope(data=response).model_dump(),
    )


@router.get("/candidates/{candidate_id}")
async def get_candidate(
    candidate_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    candidate_repo: Annotated[CandidateRepository, Depends(get_candidate_repo)],
    screening_repo: Annotated[
        ScreeningReadRepository,
        Depends(get_screening_read_repo),
    ],
) -> JSONResponse:
    candidate = await candidate_repo.get_by_id(candidate_id)
    if candidate is None:
        return JSONResponse(
            status_code=404,
            content=ErrorEnvelope(
                error=ErrorBody(code="NOT_FOUND", message="Candidate not found"),
            ).model_dump(),
        )

    screenings = await screening_repo.list_for_candidate(candidate_id)
    response = CandidateDetailResponse(
        id=candidate.id,
        name=candidate.name,
        email=candidate.email,
        phone=candidate.phone,
        location=candidate.location,
        source_filename=candidate.source_filename,
        content_hash=candidate.content_hash,
        created_at=candidate.created_at.isoformat(),
        updated_at=candidate.updated_at.isoformat(),
        parsed_cv_json=candidate.parsed_cv_json,
        screenings=[
            ScreeningResultDetail(
                overall_score=row.overall_score,
                recommendation=row.recommendation,
                criteria_scores_json=row.criteria_scores_json,
                strengths=row.strengths,
                weaknesses=row.weaknesses,
                tokens_used=row.tokens_used,
                cost_usd=row.cost_usd,
                latency_ms=row.latency_ms,
                prompt_version=row.prompt_version,
                model=row.model,
                created_at=row.created_at.isoformat(),
            )
            for row in screenings
        ],
    )
    return JSONResponse(
        status_code=200,
        content=SuccessEnvelope(data=response).model_dump(),
    )
