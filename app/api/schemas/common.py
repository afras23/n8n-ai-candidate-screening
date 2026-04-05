"""
Shared API envelope schemas.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.core.logging_config import get_correlation_id


class Metadata(BaseModel):
    """Standard response metadata."""

    model_config = ConfigDict(extra="forbid")

    correlation_id: str | None = Field(
        default=None,
        description="Correlation ID for tracing across logs and services.",
        examples=["b9b9a6c5-2b03-4ea8-8cc6-9f6a7d40a3f8"],
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="ISO-8601 timestamp for when the response was generated.",
    )


class SuccessEnvelope[T](BaseModel):
    """Success envelope for all API responses."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["success"] = "success"
    data: T
    metadata: Metadata = Field(
        default_factory=lambda: Metadata(correlation_id=get_correlation_id()),
    )


class ErrorBody(BaseModel):
    """Error payload for failure responses."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., description="Stable error code identifier.")
    message: str = Field(..., description="Human-readable error message.")
    context: dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    """Error envelope for all API responses."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["error"] = "error"
    error: ErrorBody
    metadata: Metadata = Field(
        default_factory=lambda: Metadata(correlation_id=get_correlation_id()),
    )
