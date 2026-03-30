"""Pydantic schemas for HTTP API boundaries."""

from app.api.schemas.candidates import CandidateDetailResponse, CandidateListResponse
from app.api.schemas.common import ErrorEnvelope, Metadata, SuccessEnvelope
from app.api.schemas.jobs import JobCreateRequest, JobResponse
from app.api.schemas.screening import (
    BatchScreeningResponse,
    ScreeningRequest,
    ScreeningResponse,
)

__all__ = [
    "BatchScreeningResponse",
    "CandidateDetailResponse",
    "CandidateListResponse",
    "ErrorEnvelope",
    "JobCreateRequest",
    "JobResponse",
    "Metadata",
    "ScreeningRequest",
    "ScreeningResponse",
    "SuccessEnvelope",
]
