"""
Job matching helpers (Phase 2).

Maps scored profiles to discrete routing recommendations.
"""

from __future__ import annotations

from typing import Any


async def match_candidate_to_job(
    score_payload: dict[str, Any],
    job_id: str,
) -> dict[str, Any]:
    """
    Refine scoring output into a match summary for workflow routing.

    Args:
        score_payload: Output from the scoring service.
        job_id: External or internal job identifier from n8n.

    Returns:
        Match assessment consumed by HTTP responses and integrations.

    Raises:
        NotImplementedError: Until Phase 2 implements matching rules.
    """
    raise NotImplementedError("Implemented in Phase 2")
