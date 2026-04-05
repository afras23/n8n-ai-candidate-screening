"""
Database and migration integration tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from app.models.candidate import Candidate
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


def test_alembic_migration_applies_cleanly(integration_schema_ready: None) -> None:
    """Running upgrade twice must be idempotent (no errors)."""
    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    command.upgrade(cfg, "head")
    command.upgrade(cfg, "head")


@pytest.mark.asyncio
async def test_create_and_read_candidate_record(
    integration_schema_ready: None,
    integration_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Persist a candidate row and read it back with the async session factory."""
    content_hash = "integration-test-hash-001"
    async with integration_session_factory() as session:
        existing = await session.execute(
            select(Candidate).where(Candidate.content_hash == content_hash),
        )
        for row in existing.scalars().all():
            await session.delete(row)
        await session.commit()

    async with integration_session_factory() as session:
        candidate = Candidate(
            name="Integration User",
            email="integration@example.com",
            phone=None,
            location="Remote",
            raw_cv_text="Sample CV body",
            parsed_cv_json=None,
            source_filename="cv.pdf",
            content_hash=content_hash,
        )
        session.add(candidate)
        await session.commit()
        await session.refresh(candidate)
        candidate_id = candidate.id

    async with integration_session_factory() as session:
        loaded = await session.get(Candidate, candidate_id)
        assert loaded is not None
        assert loaded.email == "integration@example.com"
        assert loaded.content_hash == content_hash
