"""
AI-backed candidate scoring (Phase 2).

Applies rubric-weighted structured LLM output to CV text.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.config import Settings
from app.core.exceptions import ScoringError
from app.core.logging_config import get_correlation_id
from app.models.job import JobRequirement
from app.services.ai.client import LlmClient
from app.services.ai.prompts import get_prompt
from app.services.parsing_service import ParsedCv

logger = logging.getLogger(__name__)


class CriterionScore(BaseModel):
    """One rubric criterion score with explanation."""

    model_config = ConfigDict(extra="forbid")

    criterion_name: str
    weight: float = Field(..., ge=0.0)
    score: int = Field(..., ge=0, le=100)
    justification: str = ""


class ScoringResult(BaseModel):
    """Structured scoring output with usage metadata."""

    model_config = ConfigDict(extra="forbid")

    overall_score: int = Field(..., ge=0, le=100)
    criteria_scores: dict[str, CriterionScore]
    strengths: list[str]
    weaknesses: list[str]
    recommendation: Literal["shortlist", "review", "reject"]
    reasoning: str
    tokens_used: int = Field(..., ge=0)
    cost_usd: float = Field(..., ge=0.0)
    latency_ms: float = Field(..., ge=0.0)
    prompt_version: str


@dataclass(frozen=True)
class _PromptBundle:
    system_prompt: str
    user_prompt: str
    prompt_version: str


def _load_cv_scoring_prompt(
    *,
    cv_text: str,
    job_requirements_json: str,
    scoring_rubric_json: str,
) -> _PromptBundle:
    system_prompt, user_prompt, version_string = get_prompt(
        "cv_scoring",
        "v1",
        job_requirements=job_requirements_json,
        scoring_rubric=scoring_rubric_json,
        cv_text=cv_text,
    )
    return _PromptBundle(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        prompt_version=version_string,
    )


def _extract_rubric_weights(scoring_rubric_json: dict[str, Any]) -> dict[str, float]:
    weights: dict[str, float] = {}
    for criterion_name, value in scoring_rubric_json.items():
        if isinstance(value, dict):
            weight_value = value.get("weight")
            if isinstance(weight_value, int | float):
                weights[str(criterion_name)] = float(weight_value)
        elif isinstance(value, int | float):
            weights[str(criterion_name)] = float(value)
    return weights


def _calculate_weighted_overall_score(
    criteria_scores: dict[str, CriterionScore],
) -> int:
    total_weight = sum(score.weight for score in criteria_scores.values())
    if total_weight <= 0:
        return 0
    weighted_sum = sum(score.weight * score.score for score in criteria_scores.values())
    return int(round(weighted_sum / total_weight))


def _recommendation_from_thresholds(
    overall_score: int,
    settings: Settings,
) -> Literal["shortlist", "review", "reject"]:
    if overall_score >= settings.shortlist_threshold:
        return "shortlist"
    if overall_score >= settings.review_threshold:
        return "review"
    return "reject"


def _parse_llm_json(llm_content: str) -> dict[str, Any]:
    try:
        payload = json.loads(llm_content)
    except json.JSONDecodeError as exc:
        raise ScoringError(
            "LLM returned non-JSON output for scoring",
            context={"error_type": type(exc).__name__},
        ) from exc
    if not isinstance(payload, dict):
        raise ScoringError(
            "LLM returned invalid scoring payload type",
            context={"payload_type": type(payload).__name__},
        )
    return payload


class CandidateScoringService:
    """Score a parsed CV against job requirements using AI."""

    def __init__(self, llm_client: LlmClient, settings: Settings) -> None:
        self._llm_client = llm_client
        self._settings = settings

    async def score_candidate(
        self,
        parsed_cv: ParsedCv,
        job: JobRequirement,
    ) -> ScoringResult:
        """
        Score a parsed CV against job requirements using AI.

        Args:
            parsed_cv: Structured CV information.
            job: Job requirement row including rubric and requirements JSON.

        Returns:
            Validated scoring result with calculated overall score.

        Raises:
            ScoringError: If the AI output cannot be validated.
        """

        cv_text = parsed_cv.model_dump_json()
        job_requirements_json = json.dumps(job.requirements_json, default=str)
        scoring_rubric_json = json.dumps(job.scoring_rubric_json, default=str)
        prompt = _load_cv_scoring_prompt(
            cv_text=cv_text,
            job_requirements_json=job_requirements_json,
            scoring_rubric_json=scoring_rubric_json,
        )
        llm_result = await self._llm_client.complete(
            prompt.system_prompt,
            prompt.user_prompt,
            prompt_version=prompt.prompt_version,
        )
        scoring_payload = _parse_llm_json(llm_result.content)

        rubric_weights = _extract_rubric_weights(job.scoring_rubric_json)
        criteria_payload = scoring_payload.get("criteria_scores")
        if not isinstance(criteria_payload, dict):
            raise ScoringError(
                "LLM scoring payload missing criteria_scores",
                context={"payload_keys": sorted(scoring_payload.keys())},
            )

        criteria_scores: dict[str, CriterionScore] = {}
        for criterion_name, raw_value in criteria_payload.items():
            if isinstance(raw_value, dict):
                raw_score = raw_value.get("score")
                raw_justification = raw_value.get("justification", "")
            else:
                raw_score = raw_value
                raw_justification = ""
            if not isinstance(raw_score, int):
                raise ScoringError(
                    "LLM returned non-integer criterion score",
                    context={"criterion_name": str(criterion_name)},
                )
            weight = rubric_weights.get(str(criterion_name), 0.0)
            criteria_scores[str(criterion_name)] = CriterionScore(
                criterion_name=str(criterion_name),
                weight=weight,
                score=raw_score,
                justification=str(raw_justification),
            )

        overall_score = _calculate_weighted_overall_score(criteria_scores)
        recommendation = _recommendation_from_thresholds(overall_score, self._settings)
        strengths = scoring_payload.get("strengths", [])
        weaknesses = scoring_payload.get("weaknesses", [])
        reasoning = scoring_payload.get("reasoning", "")
        if not isinstance(strengths, list) or not isinstance(weaknesses, list):
            raise ScoringError(
                "LLM returned invalid strengths/weaknesses",
                context={},
            )
        if not isinstance(reasoning, str):
            raise ScoringError(
                "LLM returned invalid reasoning",
                context={},
            )

        result = ScoringResult(
            overall_score=overall_score,
            criteria_scores=criteria_scores,
            strengths=[str(value) for value in strengths],
            weaknesses=[str(value) for value in weaknesses],
            recommendation=recommendation,
            reasoning=reasoning,
            tokens_used=llm_result.input_tokens + llm_result.output_tokens,
            cost_usd=llm_result.cost_usd,
            latency_ms=llm_result.latency_ms,
            prompt_version=llm_result.prompt_version,
        )
        logger.info(
            "candidate_scoring_completed",
            extra={
                "correlation_id": get_correlation_id(),
                "job_id_value": str(job.id),
                "overall_score_value": result.overall_score,
                "recommendation_value": result.recommendation,
                "input_token_count": llm_result.input_tokens,
                "output_token_count": llm_result.output_tokens,
                "openai_cost_usd": round(llm_result.cost_usd, 6),
                "latency_ms_value": round(llm_result.latency_ms, 2),
                "prompt_version_str": llm_result.prompt_version,
                "llm_model_id": llm_result.model,
            },
        )
        return result


__all__ = ["CandidateScoringService", "CriterionScore", "ScoringResult"]
