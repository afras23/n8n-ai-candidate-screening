"""
Candidate persistence helpers (Phase 2).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession


class CandidateRepository:
    """Encapsulates CRUD operations for candidates."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, candidate_id: int) -> None:
        """Fetch a candidate by primary key."""
        raise NotImplementedError("Implemented in Phase 2")
