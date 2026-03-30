"""Screening HTTP routes."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas.common import ErrorBody, ErrorEnvelope, SuccessEnvelope
from app.api.schemas.screening import BatchScreeningResponse, ScreeningResponse
from app.config import settings
from app.core.exceptions import BaseAppError
from app.dependencies import get_db
from app.integrations.ats_client import MockAtsClient
from app.integrations.email_client import MockEmailClient
from app.integrations.sheets_client import MockSheetsClient
from app.services.ai.client import LlmClient
from app.services.matching_service import JobMatchingService
from app.services.parsing_service import CvParsingService
from app.services.scoring_service import CandidateScoringService
from app.services.screening_service import ScreeningService

router = APIRouter(tags=["screening"])


def _build_screening_service() -> ScreeningService:
    llm_client = LlmClient(settings)
    parsing_service = CvParsingService(llm_client)
    scoring_service = CandidateScoringService(llm_client, settings)
    matching_service = JobMatchingService()
    return ScreeningService(
        parsing_service,
        scoring_service,
        matching_service,
        ats_client=MockAtsClient(),
        sheets_client=MockSheetsClient(),
        email_client=MockEmailClient(),
    )


def get_screening_service() -> ScreeningService:
    """Dependency provider for ScreeningService."""

    return _build_screening_service()


@router.post("/screen")
async def screen(
    db: Annotated[AsyncSession, Depends(get_db)],
    screening_service: Annotated[ScreeningService, Depends(get_screening_service)],
    file: Annotated[UploadFile, File(..., description="CV attachment file")],
    job_id: Annotated[uuid.UUID | None, Form()] = None,
    job_id_q: Annotated[uuid.UUID | None, Query(alias="job_id")] = None,
) -> JSONResponse:
    selected_job_id = job_id or job_id_q
    if selected_job_id is None:
        return JSONResponse(
            status_code=422,
            content=ErrorEnvelope(
                error=ErrorBody(code="VALIDATION_ERROR", message="job_id is required"),
            ).model_dump(),
        )

    content = await file.read()
    try:
        response = await screening_service.screen_candidate(
            db,
            cv_content=content,
            filename=file.filename or "upload",
            job_id=selected_job_id,
        )
    except BaseAppError:
        raise
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(
            status_code=500,
            content=ErrorEnvelope(
                error=ErrorBody(
                    code="INTERNAL_ERROR",
                    message="Internal server error",
                    context={"error_type": type(exc).__name__},
                ),
            ).model_dump(),
        )

    return JSONResponse(
        status_code=200,
        content=SuccessEnvelope(data=response).model_dump(mode="json"),
    )


@router.post("/screen/batch")
async def screen_batch(
    db: Annotated[AsyncSession, Depends(get_db)],
    screening_service: Annotated[ScreeningService, Depends(get_screening_service)],
    files: Annotated[list[UploadFile], File(..., description="CV files")],
    job_id: Annotated[uuid.UUID | None, Form()] = None,
    job_id_q: Annotated[uuid.UUID | None, Query(alias="job_id")] = None,
) -> JSONResponse:
    selected_job_id = job_id or job_id_q
    if selected_job_id is None:
        return JSONResponse(
            status_code=422,
            content=ErrorEnvelope(
                error=ErrorBody(code="VALIDATION_ERROR", message="job_id is required"),
            ).model_dump(),
        )

    results: list[ScreeningResponse] = []
    failures: list[dict[str, str]] = []
    for upload in files:
        try:
            content = await upload.read()
            response = await screening_service.screen_candidate(
                db,
                cv_content=content,
                filename=upload.filename or "upload",
                job_id=selected_job_id,
            )
            results.append(
                ScreeningResponse.model_validate(response.model_dump(mode="json")),
            )
        except BaseAppError as exc:
            await db.rollback()
            failures.append(
                {"filename": upload.filename or "upload", "error": exc.error_code},
            )
        except Exception as exc:  # noqa: BLE001
            await db.rollback()
            failures.append(
                {"filename": upload.filename or "upload", "error": type(exc).__name__},
            )

    return JSONResponse(
        status_code=200,
        content=SuccessEnvelope(
            data=BatchScreeningResponse(results=results, failures=failures),
        ).model_dump(mode="json"),
    )
