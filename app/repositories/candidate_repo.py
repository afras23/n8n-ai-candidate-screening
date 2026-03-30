"""
Candidate persistence helpers (Phase 2).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
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
