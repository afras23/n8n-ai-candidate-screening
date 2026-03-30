"""
Job matching helpers (Phase 2).

Maps scored profiles to discrete routing recommendations.
"""

from __future__ import annotations

import logging
import re

from pydantic import BaseModel, ConfigDict, Field

from app.core.logging_config import get_correlation_id
from app.models.job import JobRequirement
from app.services.parsing_service import ParsedCv

logger = logging.getLogger(__name__)


class MatchResult(BaseModel):
    """Deterministic CV-to-job matching signal."""

    model_config = ConfigDict(extra="forbid")

    must_have_matched: list[str] = Field(default_factory=list)
    must_have_missing: list[str] = Field(default_factory=list)
    nice_to_have_matched: list[str] = Field(default_factory=list)
    match_percentage: float = Field(..., ge=0.0, le=1.0)
    experience_match: bool
    education_match: bool


_TOKEN_RE = re.compile(r"[a-z0-9\+\#\.-]+", re.IGNORECASE)


def _normalize_tokens(text: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(text)}


def _as_string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(v).strip() for v in value if str(v).strip()]
    return []


def _requirement_matches(requirement: str, tokens: set[str]) -> bool:
    requirement_tokens = _normalize_tokens(requirement)
    if not requirement_tokens:
        return False
    if requirement_tokens.issubset(tokens):
        return True
    return any(tok in tokens for tok in requirement_tokens)


class JobMatchingService:
    """Deterministically match a parsed CV against job requirements."""

    async def match(self, parsed_cv: ParsedCv, job: JobRequirement) -> MatchResult:
        """
        Deterministic matching of CV skills against job requirements.

        Args:
            parsed_cv: Parsed CV structure.
            job: Job requirements to match against.

        Returns:
            Match result summary.
        """

        must_have = _as_string_list(job.requirements_json.get("must_have"))
        nice_to_have = _as_string_list(job.requirements_json.get("nice_to_have"))
        minimum_years = job.requirements_json.get("experience_years")
        education_requirement = str(
            job.requirements_json.get("education") or ""
        ).strip()

        skill_blob = " ".join(parsed_cv.skills)
        summary_blob = parsed_cv.summary
        experience_blob = " ".join(
            str(entry.description or "")
            + " "
            + str(entry.title or "")
            + " "
            + str(entry.company or "")
            for entry in parsed_cv.experience
        )
        combined_tokens = _normalize_tokens(
            f"{skill_blob}\n{summary_blob}\n{experience_blob}"
        )

        must_have_matched: list[str] = []
        must_have_missing: list[str] = []
        for requirement in must_have:
            if _requirement_matches(requirement, combined_tokens):
                must_have_matched.append(requirement)
            else:
                must_have_missing.append(requirement)

        nice_to_have_matched: list[str] = [
            requirement
            for requirement in nice_to_have
            if _requirement_matches(requirement, combined_tokens)
        ]

        total_must = len(must_have)
        match_percentage = (len(must_have_matched) / total_must) if total_must else 1.0

        experience_match = True
        if isinstance(minimum_years, int | float):
            experience_match = parsed_cv.total_experience_years >= float(minimum_years)

        education_match = True
        if education_requirement:
            education_text = " ".join(
                " ".join(
                    str(value or "")
                    for value in (entry.degree, entry.field, entry.institution)
                )
                for entry in parsed_cv.education
            )
            education_match = _requirement_matches(
                education_requirement, _normalize_tokens(education_text)
            )

        result = MatchResult(
            must_have_matched=must_have_matched,
            must_have_missing=must_have_missing,
            nice_to_have_matched=nice_to_have_matched,
            match_percentage=round(match_percentage, 4),
            experience_match=experience_match,
            education_match=education_match,
        )
        logger.info(
            "job_matching_completed",
            extra={
                "correlation_id": get_correlation_id(),
                "job_id_value": str(job.id),
                "must_have_total": total_must,
                "must_have_matched_count": len(must_have_matched),
                "match_percentage_value": result.match_percentage,
                "experience_match_value": result.experience_match,
                "education_match_value": result.education_match,
            },
        )
        return result


__all__ = ["JobMatchingService", "MatchResult"]
