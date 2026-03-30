"""
Read-only screening queries for API endpoints (Phase 3).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candidate import ScreeningResult


class ScreeningReadRepository:
    """Read-only queries for screening results."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_candidate(
        self,
        candidate_id: uuid.UUID,
    ) -> list[ScreeningResult]:
        """
        Load screening results for a candidate.

        Args:
            candidate_id: Candidate primary key.

        Returns:
            Screening results newest-first.
        """

        result = await self._session.execute(
            select(ScreeningResult)
            .where(ScreeningResult.candidate_id == candidate_id)
            .order_by(ScreeningResult.created_at.desc()),
        )
        return list(result.scalars().all())
