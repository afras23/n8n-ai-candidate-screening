"""
Screening API schemas.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field


class ScreeningRequest(BaseModel):
    """Request payload for screening (metadata-only; file is multipart)."""

    model_config = ConfigDict(extra="forbid")

    job_id: uuid.UUID = Field(
        ...,
        description="JobRequirement UUID to score against.",
        examples=["7f9f2b6e-0df1-4c61-bd15-8a5f0b9a55c1"],
    )


class ScreeningResponse(BaseModel):
    """Screening output returned to n8n and other clients."""

    model_config = ConfigDict(extra="forbid")

    candidate_id: uuid.UUID = Field(..., description="Candidate UUID.")
    candidate_name: str = Field(..., description="Candidate full name.")
    overall_score: int = Field(..., ge=0, le=100, description="Overall score 0-100.")
    recommendation: str = Field(
        ...,
        description="Routing recommendation.",
        examples=["shortlist", "review", "reject"],
    )
    match_percentage: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Must-have match fraction (0-1).",
    )
    must_have_missing: list[str] = Field(
        default_factory=list,
        description="Must-have requirements the candidate is missing.",
    )
    cost_usd: float = Field(..., ge=0.0, description="LLM cost for this CV.")
    latency_ms: float = Field(..., ge=0.0, description="End-to-end processing time.")
    routed_to: str = Field(
        ...,
        description="Action taken by routing (ATS update, rejection email, etc.).",
    )


class BatchScreeningResponse(BaseModel):
    """Batch screening response (one response per file)."""

    model_config = ConfigDict(extra="forbid")

    results: list[ScreeningResponse] = Field(
        default_factory=list,
        description="Successful screening results.",
    )
    failures: list[dict[str, str]] = Field(
        default_factory=list,
        description="Per-file failures (filename + error).",
        examples=[[{"filename": "cv.pdf", "error": "PARSING_FAILED"}]],
    )
