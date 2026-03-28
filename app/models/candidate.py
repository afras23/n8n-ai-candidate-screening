"""
Candidate and screening result ORM models.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Uuid

from app.models.base import Base


def _utc_now() -> datetime:
    return datetime.now(UTC)


class Candidate(Base):
    """Inbound applicant with parsed CV payload and dedupe hash."""

    __tablename__ = "candidates"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    email: Mapped[str] = mapped_column(String(512), nullable=False, default="")
    phone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    location: Mapped[str | None] = mapped_column(String(512), nullable=True)
    raw_cv_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    parsed_cv_json: Mapped[dict[str, object] | None] = mapped_column(
        JSON,
        nullable=True,
    )
    source_filename: Mapped[str] = mapped_column(
        String(1024),
        nullable=False,
        default="",
    )
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
        onupdate=_utc_now,
    )


class ScreeningResult(Base):
    """Persisted output of an AI screening run for a candidate and job."""

    __tablename__ = "screening_results"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("candidates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("job_requirements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    overall_score: Mapped[int] = mapped_column(Integer, nullable=False)
    criteria_scores_json: Mapped[dict[str, object]] = mapped_column(
        JSON,
        nullable=False,
    )
    strengths_json: Mapped[list[object]] = mapped_column(JSON, nullable=False)
    weaknesses_json: Mapped[list[object]] = mapped_column(JSON, nullable=False)
    recommendation: Mapped[str] = mapped_column(String(32), nullable=False)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    prompt_version: Mapped[str] = mapped_column(String(128), nullable=False)
    openai_model: Mapped[str] = mapped_column("model", String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=_utc_now,
    )
