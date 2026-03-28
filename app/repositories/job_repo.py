"""
Job persistence helpers (Phase 2).
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession


class JobRepository:
    """Encapsulates lookups for job postings."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_external_id(self, external_job_id: str) -> None:
        """Load a job using the identifier supplied by n8n or the ATS."""
        raise NotImplementedError("Implemented in Phase 2")
