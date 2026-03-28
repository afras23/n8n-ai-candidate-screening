"""
AI-backed candidate scoring (Phase 2).

Applies rubric-weighted structured LLM output to CV text.
"""

from __future__ import annotations

from typing import Any


async def score_candidate_profile(
    cv_text: str,
    job_requirements: dict[str, Any],
    scoring_rubric: dict[str, Any],
) -> dict[str, Any]:
    """
    Produce a structured score and breakdown for a candidate.

    Args:
        cv_text: Normalised CV text from the parsing layer.
        job_requirements: Must-have and nice-to-have criteria for the role.
        scoring_rubric: Weighted criteria describing scoring dimensions.

    Returns:
        Validated scoring payload for API responses.

    Raises:
        NotImplementedError: Until Phase 2 wires the AI client.
    """
    raise NotImplementedError("Implemented in Phase 2")
