"""
End-to-end screening orchestration (Phase 2).

Coordinates parsing, scoring, matching, and persistence boundaries.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from pathlib import PurePath
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import MatchingError
from app.core.logging_config import get_correlation_id
from app.integrations.ats_client import AtsClient
from app.integrations.email_client import EmailClient
from app.integrations.sheets_client import SheetsClient
from app.models.candidate import Candidate, ScreeningResult
from app.repositories.candidate_repo import CandidateRepository
from app.repositories.job_repo import JobRepository
from app.repositories.screening_repo import ScreeningRepository
from app.services.matching_service import JobMatchingService, MatchResult
from app.services.parsing_service import (
    CvParsingService,
    compute_content_hash,
    parse_file,
)
from app.services.scoring_service import CandidateScoringService, ScoringResult

logger = logging.getLogger(__name__)


class ScreeningResponse(BaseModel):
    """API response for a completed screening run."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: uuid.UUID
    candidate_name: str
    overall_score: int = Field(..., ge=0, le=100)
    recommendation: str
    match_percentage: float = Field(..., ge=0.0, le=1.0)
    must_have_missing: list[str]
    cost_usd: float = Field(..., ge=0.0)
    latency_ms: float = Field(..., ge=0.0)
    routed_to: str


def _route_for_recommendation(
    recommendation: Literal["shortlist", "review", "reject"],
) -> str:
    if recommendation == "shortlist":
        return "ats_shortlisted"
    if recommendation == "review":
        return "ats_review"
    return "email_rejection"


def _sanitize_filename(filename: str) -> str:
    candidate = PurePath(filename).name
    return candidate[:255] if candidate else "upload"


class ScreeningService:
    """Coordinates the screening pipeline behind HTTP routes."""

    def __init__(
        self,
        parsing_service: CvParsingService,
        scoring_service: CandidateScoringService,
        matching_service: JobMatchingService,
        *,
        ats_client: AtsClient,
        sheets_client: SheetsClient,
        email_client: EmailClient,
    ) -> None:
        self._parsing_service = parsing_service
        self._scoring_service = scoring_service
        self._matching_service = matching_service
        self._ats_client = ats_client
        self._sheets_client = sheets_client
        self._email_client = email_client

    async def screen_candidate(
        self,
        session: AsyncSession,
        cv_content: bytes,
        filename: str,
        job_id: uuid.UUID,
    ) -> ScreeningResponse:
        """
        Full screening pipeline: parse → score → match → route → notify.

        Args:
            session: Async DB session (unit of work boundary).
            cv_content: Raw CV file bytes.
            filename: Original filename.
            job_id: Job requirement primary key.

        Returns:
            ScreeningResponse for API callers.

        Raises:
            ParsingError: When file parsing or CV AI parsing fails.
            ScoringError: When AI scoring fails.
            MatchingError: When deterministic matching fails.
        """

        candidate_repo = CandidateRepository(session)
        job_repo = JobRepository(session)
        screening_repo = ScreeningRepository(session)

        safe_filename = _sanitize_filename(filename)
        raw_cv_text = parse_file(cv_content, safe_filename)
        parsed_cv = await self._parsing_service.parse_cv(raw_cv_text, filename)

        content_hash = compute_content_hash(raw_cv_text)
        existing_candidate = await candidate_repo.get_by_content_hash(content_hash)
        if existing_candidate is not None:
            logger.info(
                "screening_duplicate_cv_skipped",
                extra={
                    "correlation_id": get_correlation_id(),
                    "candidate_id_value": str(existing_candidate.id),
                    "content_hash_value": content_hash,
                },
            )
            return ScreeningResponse(
                candidate_id=existing_candidate.id,
                candidate_name=existing_candidate.name,
                overall_score=0,
                recommendation="duplicate_skipped",
                match_percentage=0.0,
                must_have_missing=[],
                cost_usd=0.0,
                latency_ms=0.0,
                routed_to="skipped_duplicate",
            )

        job = await job_repo.get_by_id(job_id)
        if job is None:
            raise MatchingError(
                "Job requirement not found",
                context={"job_id": str(job_id)},
            )

        scoring_result: ScoringResult = await self._scoring_service.score_candidate(
            parsed_cv,
            job,
        )
        try:
            match_result: MatchResult = await self._matching_service.match(
                parsed_cv, job
            )
        except ValueError as exc:
            raise MatchingError(
                "Job matching failed",
                context={"error_type": type(exc).__name__},
            ) from exc

        candidate_row = Candidate(
            name=parsed_cv.name or "",
            email=parsed_cv.email or "",
            phone=parsed_cv.phone,
            location=parsed_cv.location,
            raw_cv_text=raw_cv_text,
            parsed_cv_json=parsed_cv.model_dump(),
            source_filename=safe_filename,
            content_hash=content_hash,
        )
        await candidate_repo.create(candidate_row)

        screening_row = ScreeningResult(
            candidate_id=candidate_row.id,
            job_id=job.id,
            overall_score=scoring_result.overall_score,
            criteria_scores_json={
                key: value.model_dump()
                for key, value in scoring_result.criteria_scores.items()
            },
            strengths=scoring_result.strengths,
            weaknesses=scoring_result.weaknesses,
            recommendation=scoring_result.recommendation,
            tokens_used=scoring_result.tokens_used,
            cost_usd=scoring_result.cost_usd,
            latency_ms=scoring_result.latency_ms,
            prompt_version=scoring_result.prompt_version,
            model=self._scoring_service._settings.ai_model,  # noqa: SLF001
            created_at=datetime.now(UTC),
        )
        await screening_repo.create(screening_row)

        route_action = _route_for_recommendation(scoring_result.recommendation)
        if scoring_result.recommendation in {"shortlist", "review"}:
            status = (
                "shortlisted"
                if scoring_result.recommendation == "shortlist"
                else "review"
            )
            try:
                await self._ats_client.update_status(str(candidate_row.id), status)
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "ats_update_status_failed",
                    extra={
                        "correlation_id": get_correlation_id(),
                        "candidate_id_value": str(candidate_row.id),
                        "status_value": status,
                        "error_type": type(exc).__name__,
                    },
                )
        else:
            try:
                await self._email_client.send_rejection(
                    candidate_email=candidate_row.email,
                    candidate_name=candidate_row.name,
                    job_title=job.title,
                )
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "email_rejection_failed",
                    extra={
                        "correlation_id": get_correlation_id(),
                        "candidate_id_value": str(candidate_row.id),
                        "error_type": type(exc).__name__,
                    },
                )

        try:
            await self._sheets_client.append_row(
                {
                    "candidate_name": candidate_row.name,
                    "candidate_email": candidate_row.email,
                    "job_title": job.title,
                    "overall_score": str(scoring_result.overall_score),
                    "recommendation": scoring_result.recommendation,
                    "match_percentage": str(match_result.match_percentage),
                    "timestamp": datetime.now(UTC).isoformat(),
                }
            )
        except Exception as exc:  # noqa: BLE001
            logger.error(
                "sheets_append_row_failed",
                extra={
                    "correlation_id": get_correlation_id(),
                    "candidate_id_value": str(candidate_row.id),
                    "error_type": type(exc).__name__,
                },
            )

        logger.info(
            "screening_pipeline_completed",
            extra={
                "correlation_id": get_correlation_id(),
                "candidate_id_value": str(candidate_row.id),
                "job_id_value": str(job.id),
                "overall_score_value": scoring_result.overall_score,
                "recommendation_value": scoring_result.recommendation,
                "match_percentage_value": match_result.match_percentage,
                "routed_to_value": route_action,
                "openai_cost_usd": round(scoring_result.cost_usd, 6),
                "latency_ms_value": round(scoring_result.latency_ms, 2),
            },
        )
        return ScreeningResponse(
            candidate_id=candidate_row.id,
            candidate_name=candidate_row.name,
            overall_score=scoring_result.overall_score,
            recommendation=scoring_result.recommendation,
            match_percentage=match_result.match_percentage,
            must_have_missing=match_result.must_have_missing,
            cost_usd=scoring_result.cost_usd,
            latency_ms=scoring_result.latency_ms,
            routed_to=route_action,
        )

    async def run_screening(
        self,
        cv_bytes: bytes,
        filename: str,
        job_id: str,
    ) -> dict[str, Any]:
        """
        Execute parse → score → match for a single application.

        Args:
            cv_bytes: Raw CV attachment bytes.
            filename: Original attachment filename.
            job_id: Target job identifier supplied by n8n.

        Returns:
            API-ready screening result payload.

        Raises:
            NotImplementedError: Until Phase 2 implements the workflow.
        """
        raise NotImplementedError("Use screen_candidate(...) with DB session")
