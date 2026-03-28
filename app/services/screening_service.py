"""
End-to-end screening orchestration (Phase 2).

Coordinates parsing, scoring, matching, and persistence boundaries.
"""

from __future__ import annotations

from typing import Any


class ScreeningService:
    """Coordinates the screening pipeline behind HTTP routes."""

    async def run_screening(
        self,
        cv_bytes: bytes,
        filename: str,
        job_id: str,
    ) -> dict[str, Any]:
        """
        Execute parse → score → match for a single application.

        Args:
            cv_bytes: Raw CV attachment bytes.
            filename: Original attachment filename.
            job_id: Target job identifier supplied by n8n.

        Returns:
            API-ready screening result payload.

        Raises:
            NotImplementedError: Until Phase 2 implements the workflow.
        """
        raise NotImplementedError("Implemented in Phase 2")
