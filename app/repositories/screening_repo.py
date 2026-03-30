"""
Screening audit and outcome persistence (Phase 2).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candidate import ScreeningResult


class ScreeningRepository:
    """Persists screening runs for analytics and compliance."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, screening_result: ScreeningResult) -> ScreeningResult:
        """
        Persist a screening result row.

        Args:
            screening_result: ScreeningResult ORM instance.

        Returns:
            The persisted instance (with primary key populated).
        """

        self._session.add(screening_result)
        await self._session.flush()
        return screening_result
