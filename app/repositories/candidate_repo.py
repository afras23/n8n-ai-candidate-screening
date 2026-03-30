"""
Candidate persistence helpers (Phase 2).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candidate import Candidate


class CandidateRepository:
    """Encapsulates CRUD operations for candidates."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, candidate_id: uuid.UUID) -> Candidate | None:
        """
        Fetch a candidate by primary key.

        Args:
            candidate_id: Candidate primary key.

        Returns:
            Candidate if found, else None.
        """

        return await self._session.get(Candidate, candidate_id)

    async def get_by_content_hash(self, content_hash: str) -> Candidate | None:
        """
        Fetch a candidate by content hash (deduplication).

        Args:
            content_hash: Stable digest of normalized CV text.

        Returns:
            Candidate if found, else None.
        """

        result = await self._session.execute(
            select(Candidate).where(Candidate.content_hash == content_hash),
        )
        return result.scalar_one_or_none()

    async def create(self, candidate: Candidate) -> Candidate:
        """
        Persist a new candidate row.

        Args:
            candidate: Candidate ORM instance.

        Returns:
            The persisted instance (with primary key populated).
        """

        self._session.add(candidate)
        await self._session.flush()
        return candidate

    async def list_candidates(
        self,
        *,
        offset: int,
        limit: int,
        job_id: uuid.UUID | None = None,
        recommendation: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> list[Candidate]:
        """
        List candidates for pagination.

        Args:
            offset: Row offset.
            limit: Page size.

        Returns:
            Candidate rows ordered by created_at descending.
        """

        stmt = select(Candidate)
        if created_from is not None:
            stmt = stmt.where(Candidate.created_at >= created_from)
        if created_to is not None:
            stmt = stmt.where(Candidate.created_at <= created_to)
        if job_id is not None or recommendation is not None:
            from sqlalchemy import exists

            from app.models.candidate import ScreeningResult

            sub = select(ScreeningResult.id).where(
                ScreeningResult.candidate_id == Candidate.id
            )
            if job_id is not None:
                sub = sub.where(ScreeningResult.job_id == job_id)
            if recommendation is not None:
                sub = sub.where(ScreeningResult.recommendation == recommendation)
            stmt = stmt.where(exists(sub))

        result = await self._session.execute(
            stmt.order_by(Candidate.created_at.desc()).offset(offset).limit(limit),
        )
        return list(result.scalars().all())

    async def count_candidates(
        self,
        *,
        job_id: uuid.UUID | None = None,
        recommendation: str | None = None,
    ) -> int:
        """
        Count total candidates.

        Returns:
            Total number of candidate rows.
        """

        stmt = select(func.count()).select_from(Candidate)
        if job_id is not None or recommendation is not None:
            from sqlalchemy import exists

            from app.models.candidate import ScreeningResult

            sub = select(ScreeningResult.id).where(
                ScreeningResult.candidate_id == Candidate.id
            )
            if job_id is not None:
                sub = sub.where(ScreeningResult.job_id == job_id)
            if recommendation is not None:
                sub = sub.where(ScreeningResult.recommendation == recommendation)
            stmt = stmt.where(exists(sub))

        result = await self._session.execute(stmt)
        count_value = result.scalar_one()
        return int(count_value)
