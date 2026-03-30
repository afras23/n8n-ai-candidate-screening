"""
Candidate API schemas.
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class CandidateSummary(BaseModel):
    """One candidate row in list endpoints."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    name: str
    email: str
    created_at: str


class CandidateListResponse(BaseModel):
    """Paginated list of candidates."""

    model_config = ConfigDict(extra="forbid")

    items: list[CandidateSummary] = Field(default_factory=list)
    page: int = Field(..., ge=1)
    page_size: int = Field(..., ge=1, le=200)
    total: int = Field(..., ge=0)


class ScreeningResultDetail(BaseModel):
    """Screening details attached to a candidate."""

    model_config = ConfigDict(extra="forbid")

    overall_score: int = Field(..., ge=0, le=100)
    recommendation: str
    criteria_scores_json: dict[str, Any]
    strengths: list[Any]
    weaknesses: list[Any]
    tokens_used: int
    cost_usd: float
    latency_ms: float
    prompt_version: str
    model: str
    created_at: str


class CandidateDetailResponse(BaseModel):
    """Candidate detail response with screening history."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID
    name: str
    email: str
    phone: str | None
    location: str | None
    source_filename: str
    content_hash: str
    created_at: str
    updated_at: str
    parsed_cv_json: dict[str, Any] | None
    screenings: list[ScreeningResultDetail] = Field(default_factory=list)
