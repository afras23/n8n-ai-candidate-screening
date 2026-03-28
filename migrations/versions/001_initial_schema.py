"""Initial schema for candidates, jobs, and screening results.

Revision ID: 001_initial
Revises:
Create Date: 2026-03-28

"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "job_requirements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("requirements_json", sa.JSON(), nullable=False),
        sa.Column("scoring_rubric_json", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("email", sa.String(length=512), nullable=False),
        sa.Column("phone", sa.String(length=64), nullable=True),
        sa.Column("location", sa.String(length=512), nullable=True),
        sa.Column("raw_cv_text", sa.Text(), nullable=False),
        sa.Column("parsed_cv_json", sa.JSON(), nullable=True),
        sa.Column("source_filename", sa.String(length=1024), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_hash"),
    )
    op.create_table(
        "screening_results",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("overall_score", sa.Integer(), nullable=False),
        sa.Column("criteria_scores_json", sa.JSON(), nullable=False),
        sa.Column("strengths_json", sa.JSON(), nullable=False),
        sa.Column("weaknesses_json", sa.JSON(), nullable=False),
        sa.Column("recommendation", sa.String(length=32), nullable=False),
        sa.Column("tokens_used", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Float(), nullable=False),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("prompt_version", sa.String(length=128), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidates.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["job_id"],
            ["job_requirements.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_screening_results_candidate_id",
        "screening_results",
        ["candidate_id"],
        unique=False,
    )
    op.create_index(
        "ix_screening_results_job_id",
        "screening_results",
        ["job_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_screening_results_job_id", table_name="screening_results")
    op.drop_index("ix_screening_results_candidate_id", table_name="screening_results")
    op.drop_table("screening_results")
    op.drop_table("candidates")
    op.drop_table("job_requirements")
