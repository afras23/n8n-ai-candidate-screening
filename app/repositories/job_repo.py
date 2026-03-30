"""
Job persistence helpers (Phase 2).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import JobRequirement


class JobRepository:
    """Encapsulates lookups for job postings."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, job_id: uuid.UUID) -> JobRequirement | None:
        """
        Load a job requirement row by primary key.

        Args:
            job_id: JobRequirement primary key.

        Returns:
            JobRequirement if found, else None.
        """

        return await self._session.get(JobRequirement, job_id)

    async def get_active_by_title(self, title: str) -> JobRequirement | None:
        """
        Load an active job requirement row by exact title.

        Args:
            title: Job title.

        Returns:
            JobRequirement if found, else None.
        """

        result = await self._session.execute(
            select(JobRequirement).where(
                JobRequirement.title == title,
                JobRequirement.is_active.is_(True),
            ),
        )
        return result.scalar_one_or_none()

    async def list_active(self) -> list[JobRequirement]:
        """
        List all active job requirements.

        Returns:
            Active job requirements sorted by creation time descending.
        """

        result = await self._session.execute(
            select(JobRequirement)
            .where(JobRequirement.is_active.is_(True))
            .order_by(JobRequirement.created_at.desc()),
        )
        return list(result.scalars().all())
