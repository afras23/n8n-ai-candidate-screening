"""
Screening audit and outcome persistence (Phase 2).
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession


class ScreeningRepository:
    """Persists screening runs for analytics and compliance."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record_screening_outcome(self, payload: dict[str, Any]) -> None:
        """Insert or update a screening audit row."""
        raise NotImplementedError("Implemented in Phase 2")
