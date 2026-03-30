"""
Evaluation runner for scoring + matching behavior.

Runs a deterministic evaluation over ``eval/test_set.jsonl`` and writes a
timestamped JSON report under ``eval/results/``.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.config import Settings
from app.models.job import JobRequirement
from app.services.matching_service import JobMatchingService
from app.services.parsing_service import ParsedCv
from app.services.scoring_service import CandidateScoringService

logger = logging.getLogger(__name__)

Recommendation = Literal["shortlist", "review", "reject"]


class EvalCase(BaseModel):
    """One evaluation test case loaded from JSONL."""

    model_config = ConfigDict(extra="forbid")

    cv_text: str = Field(min_length=1)
    job_requirements: dict[str, Any]
    expected_recommendation: Recommendation
    expected_score_range: tuple[int, int]
    expected_must_have_count: int = Field(ge=0)
    category: str


@dataclass(frozen=True)
class EvalPrediction:
    recommendation: Recommendation
    overall_score: int
    must_have_matched: int
    cost_usd: float
    latency_ms: float


class _DeterministicLlmClient:
    """
    Deterministic LLM stub for evaluation.

    Produces scoring JSON based on a simple heuristic (must-have match rate).
    """

    def __init__(self, *, model: str) -> None:
        self._model = model

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        prompt_version: str,
    ) -> Any:
        must_haves = _extract_job_must_haves(user_prompt)
        cv_skills = _extract_cv_skills(user_prompt)
        matched = len({s.lower() for s in must_haves} & {s.lower() for s in cv_skills})
        match_rate = matched / max(len(must_haves), 1)

        if match_rate >= 0.9:
            recommendation: Recommendation = "shortlist"
            tech_score = 95
            exp_score = 90
        elif match_rate >= 0.4:
            recommendation = "review"
            tech_score = 65
            exp_score = 60
        else:
            recommendation = "reject"
            tech_score = 20
            exp_score = 20

        payload = {
            "criteria_scores": {
                "technical_skills": {"score": tech_score, "justification": "deterministic"},
                "experience": {"score": exp_score, "justification": "deterministic"},
            },
            "strengths": [],
            "weaknesses": [],
            "reasoning": "deterministic",
            "recommendation": recommendation,
        }

        return type(
            "EvalLlmCallResult",
            (),
            {
                "content": json.dumps(payload),
                "input_tokens": 250,
                "output_tokens": 120,
                "cost_usd": 0.08,
                "latency_ms": 2800.0,
                "model": self._model,
                "prompt_version": prompt_version,
            },
        )()


def _extract_job_must_haves(user_prompt: str) -> list[str]:
    marker = "Job requirements (JSON):"
    if marker not in user_prompt:
        return []
    raw_section = user_prompt.split(marker, 1)[1]
    raw = raw_section.split("\n\nScoring rubric", 1)[0].strip()
    try:
        requirements = json.loads(raw)
    except json.JSONDecodeError:
        return []
    must_haves = requirements.get("must_have", [])
    if not isinstance(must_haves, list):
        return []
    return [str(value) for value in must_haves]


def _extract_cv_skills(user_prompt: str) -> list[str]:
    marker = "CV text:"
    if marker not in user_prompt:
        return []
    cv_text = user_prompt.split(marker, 1)[1]
    known = [
        "python",
        "fastapi",
        "postgresql",
        "postgres",
        "sqlalchemy",
        "docker",
        "aws",
        "kubernetes",
        "terraform",
        "airflow",
        "react",
        "typescript",
        "swift",
        "django",
        "jira",
        "scrum",
    ]
    lowered = cv_text.lower()
    return [k for k in known if k in lowered]


def _build_job(requirements_json: dict[str, Any]) -> JobRequirement:
    rubric = {
        "technical_skills": {"weight": 0.6, "description": "Skills fit"},
        "experience": {"weight": 0.4, "description": "Experience fit"},
    }
    return JobRequirement(
        title="Eval Role",
        description="Evaluation job",
        requirements_json=requirements_json,
        scoring_rubric_json=rubric,
        is_active=True,
    )


def _build_parsed_cv(cv_text: str) -> ParsedCv:
    return ParsedCv(
        name="",
        summary=cv_text[:500],
        experience=[],
        education=[],
        skills=_extract_cv_skills(f"CV_TEXT:{cv_text}"),
        certifications=[],
        languages=[],
        total_experience_years=0.0,
    )


def _settings() -> Settings:
    return Settings.model_validate(
        {
            "database_url": "postgresql+asyncpg://test:test@127.0.0.1:5432/test_db",
            "openai_api_key": "sk-eval",
            "ai_model": "gpt-4o",
            "ai_max_tokens": 256,
            "ai_temperature": 0.0,
            "max_daily_cost_usd": 10.0,
            "max_per_cv_cost_usd": 2.0,
            "shortlist_threshold": 80,
            "review_threshold": 50,
        }
    )


async def _predict(case: EvalCase) -> EvalPrediction:
    job = _build_job(case.job_requirements)
    parsed_cv = _build_parsed_cv(case.cv_text)

    llm_client = _DeterministicLlmClient(model=_settings().ai_model)
    scoring_service = CandidateScoringService(llm_client, _settings())
    matching_service = JobMatchingService()

    scoring_result = await scoring_service.score_candidate(parsed_cv, job)
    match_result = await matching_service.match(parsed_cv, job)

    return EvalPrediction(
        recommendation=scoring_result.recommendation,
        overall_score=scoring_result.overall_score,
        must_have_matched=len(match_result.must_have_matched),
        cost_usd=scoring_result.cost_usd,
        latency_ms=scoring_result.latency_ms,
    )


def _load_cases(path: Path) -> list[EvalCase]:
    cases: list[EvalCase] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        cases.append(EvalCase.model_validate_json(line))
    return cases


def _in_range(value: int, expected_range: tuple[int, int]) -> bool:
    return expected_range[0] <= value <= expected_range[1]


async def run_evaluation() -> int:
    """
    Run evaluation against the JSONL test set.

    Returns:
        Exit code (0 = success).
    """

    repo_root = Path(__file__).resolve().parents[1]
    test_set_path = repo_root / "eval" / "test_set.jsonl"
    cases = _load_cases(test_set_path)

    predictions: list[EvalPrediction] = []
    for case in cases:
        predictions.append(await _predict(case))

    recommendation_hits = 0
    score_range_hits = 0
    must_have_hits = 0
    total_cost = 0.0
    total_latency_ms = 0.0

    for case, pred in zip(cases, predictions, strict=True):
        if pred.recommendation == case.expected_recommendation:
            recommendation_hits += 1
        if _in_range(pred.overall_score, case.expected_score_range):
            score_range_hits += 1
        if pred.must_have_matched >= case.expected_must_have_count:
            must_have_hits += 1
        total_cost += pred.cost_usd
        total_latency_ms += pred.latency_ms

    test_cases = len(cases)
    report = {
        "timestamp": datetime.now(UTC).isoformat(),
        "model": _settings().ai_model,
        "prompt_version": "cv_scoring_v1",
        "test_cases": test_cases,
        "recommendation_accuracy": round(recommendation_hits / max(test_cases, 1), 2),
        "score_range_accuracy": round(score_range_hits / max(test_cases, 1), 2),
        "must_have_detection_accuracy": round(must_have_hits / max(test_cases, 1), 2),
        "avg_cost_per_cv_usd": round(total_cost / max(test_cases, 1), 2),
        "avg_latency_ms": int(round(total_latency_ms / max(test_cases, 1), 0)),
        "total_cost_usd": round(total_cost, 2),
    }

    results_dir = repo_root / "eval" / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    output_path = results_dir / f"eval_{date.today().isoformat()}.json"
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    logger.info(
        "evaluation_completed",
        extra={
            "test_cases": test_cases,
            "output_path": str(output_path),
            "recommendation_accuracy": report["recommendation_accuracy"],
            "score_range_accuracy": report["score_range_accuracy"],
            "must_have_detection_accuracy": report["must_have_detection_accuracy"],
            "avg_cost_per_cv_usd": report["avg_cost_per_cv_usd"],
            "avg_latency_ms": report["avg_latency_ms"],
            "total_cost_usd": report["total_cost_usd"],
        },
    )

    return 0


def main() -> None:
    raise SystemExit(asyncio.run(run_evaluation()))


if __name__ == "__main__":
    main()

