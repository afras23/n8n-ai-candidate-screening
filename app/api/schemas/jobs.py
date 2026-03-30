"""
Job API schemas.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class JobCreateRequest(BaseModel):
    """Create a new job requirement and rubric."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(
        ...,
        description="Job title.",
        examples=["Senior Python Developer"],
    )
    description: str = Field("", description="Job description text.")
    requirements_json: dict[str, Any] = Field(
        ...,
        description="Structured requirements (must_have, nice_to_have, etc.).",
        examples=[
            {
                "must_have": ["Python", "FastAPI"],
                "nice_to_have": ["AWS"],
                "experience_years": 4,
                "education": "Computer Science or equivalent",
            }
        ],
    )
    scoring_rubric_json: dict[str, Any] = Field(
        ...,
        description="Rubric with weights per criterion.",
        examples=[{"technical_skills": {"weight": 0.5, "description": "Skills match"}}],
    )


class JobResponse(BaseModel):
    """Job requirement response."""

    model_config = ConfigDict(extra="forbid")

    id: uuid.UUID = Field(..., description="JobRequirement UUID.")
    title: str = Field(..., description="Job title.")
    description: str = Field(..., description="Job description.")
    requirements_json: dict[str, Any] = Field(
        ...,
        description="Structured requirements.",
    )
    scoring_rubric_json: dict[str, Any] = Field(..., description="Scoring rubric.")
    is_active: bool = Field(..., description="Whether the job is active.")
    created_at: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="Created timestamp.",
    )
