"""
Unit tests for scoring service (Phase 2).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from app.config import Settings
from app.models.job import JobRequirement
from app.services.parsing_service import ParsedCv
from app.services.scoring_service import CandidateScoringService


def _settings(**overrides: object) -> Settings:
    base = {
        "database_url": "postgresql+asyncpg://test:test@127.0.0.1:5432/test_db",
        "openai_api_key": "sk-test",
        "shortlist_threshold": 80,
        "review_threshold": 50,
    }
    base.update(overrides)
    return Settings.model_validate(base)


def _job() -> JobRequirement:
    return JobRequirement(
        title="Senior Python Developer",
        description="x",
        requirements_json={"must_have": ["Python"], "nice_to_have": ["AWS"]},
        scoring_rubric_json={
            "technical_skills": {"weight": 0.5, "description": "x"},
            "experience": {"weight": 0.5, "description": "y"},
        },
        is_active=True,
    )


@pytest.mark.asyncio
async def test_scores_candidate_with_rubric() -> None:
    llm_client = MagicMock()
    llm_client.complete = AsyncMock(
        return_value=MagicMock(
            content=(
                '{"criteria_scores":{"technical_skills":{"score":90,"justification":"ok"},'
                '"experience":{"score":70,"justification":"ok"}},'
                '"strengths":["a"],"weaknesses":["b"],"reasoning":"c",'
                '"recommendation":"shortlist"}'
            ),
            input_tokens=10,
            output_tokens=10,
            cost_usd=0.01,
            latency_ms=10.0,
            model="gpt-4o",
            prompt_version="cv_scoring_v1",
        )
    )
    service = CandidateScoringService(llm_client, _settings())
    result = await service.score_candidate(ParsedCv(name="x"), _job())
    assert result.criteria_scores["technical_skills"].weight == 0.5
    assert result.overall_score == 80


@pytest.mark.asyncio
async def test_recommendation_based_on_thresholds() -> None:
    llm_client = MagicMock()
    llm_client.complete = AsyncMock(
        return_value=MagicMock(
            content=(
                '{"criteria_scores":{"technical_skills":{"score":49,"justification":"x"},'
                '"experience":{"score":49,"justification":"y"}},'
                '"strengths":[],"weaknesses":[],"reasoning":"z","recommendation":"reject"}'
            ),
            input_tokens=1,
            output_tokens=1,
            cost_usd=0.0,
            latency_ms=1.0,
            model="gpt-4o",
            prompt_version="cv_scoring_v1",
        )
    )
    service = CandidateScoringService(
        llm_client,
        _settings(shortlist_threshold=80, review_threshold=50),
    )
    result = await service.score_candidate(ParsedCv(name="x"), _job())
    assert result.recommendation == "reject"


@pytest.mark.asyncio
async def test_weighted_score_calculation() -> None:
    llm_client = MagicMock()
    llm_client.complete = AsyncMock(
        return_value=MagicMock(
            content=(
                '{"criteria_scores":{"technical_skills":{"score":100,"justification":"x"},'
                '"experience":{"score":0,"justification":"y"}},'
                '"strengths":[],"weaknesses":[],"reasoning":"z","recommendation":"review"}'
            ),
            input_tokens=1,
            output_tokens=1,
            cost_usd=0.0,
            latency_ms=1.0,
            model="gpt-4o",
            prompt_version="cv_scoring_v1",
        )
    )
    service = CandidateScoringService(llm_client, _settings(review_threshold=40))
    result = await service.score_candidate(ParsedCv(name="x"), _job())
    assert result.overall_score == 50


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tech", "exp", "expected"),
    [
        (95, 95, "shortlist"),
        (60, 60, "review"),
        (10, 10, "reject"),
    ],
)
async def test_parametrized_recommendations(
    tech: int,
    exp: int,
    expected: str,
) -> None:
    llm_client = MagicMock()
    llm_client.complete = AsyncMock(
        return_value=MagicMock(
            content=(
                '{"criteria_scores":{"technical_skills":{"score":'
                + str(tech)
                + ',"justification":"x"},"experience":{"score":'
                + str(exp)
                + ',"justification":"y"}},'
                '"strengths":[],"weaknesses":[],"reasoning":"z","recommendation":"review"}'
            ),
            input_tokens=1,
            output_tokens=1,
            cost_usd=0.0,
            latency_ms=1.0,
            model="gpt-4o",
            prompt_version="cv_scoring_v1",
        )
    )
    service = CandidateScoringService(llm_client, _settings())
    result = await service.score_candidate(ParsedCv(name="x"), _job())
    assert result.recommendation == expected


@pytest.mark.asyncio
async def test_perfect_candidate_scores_above_threshold() -> None:
    llm_client = MagicMock()
    llm_client.complete = AsyncMock(
        return_value=MagicMock(
            content=(
                '{"criteria_scores":{"technical_skills":{"score":100,"justification":"x"},'
                '"experience":{"score":100,"justification":"y"}},'
                '"strengths":["a"],"weaknesses":[],"reasoning":"z","recommendation":"shortlist"}'
            ),
            input_tokens=1,
            output_tokens=1,
            cost_usd=0.01,
            latency_ms=1.0,
            model="gpt-4o",
            prompt_version="cv_scoring_v1",
        )
    )
    service = CandidateScoringService(llm_client, _settings(shortlist_threshold=80))
    result = await service.score_candidate(ParsedCv(name="x"), _job())
    assert result.overall_score >= 80
    assert result.recommendation == "shortlist"


@pytest.mark.asyncio
async def test_unqualified_candidate_scores_below_threshold() -> None:
    llm_client = MagicMock()
    llm_client.complete = AsyncMock(
        return_value=MagicMock(
            content=(
                '{"criteria_scores":{"technical_skills":{"score":0,"justification":"x"},'
                '"experience":{"score":0,"justification":"y"}},'
                '"strengths":[],"weaknesses":["a"],"reasoning":"z","recommendation":"reject"}'
            ),
            input_tokens=1,
            output_tokens=1,
            cost_usd=0.0,
            latency_ms=1.0,
            model="gpt-4o",
            prompt_version="cv_scoring_v1",
        )
    )
    service = CandidateScoringService(llm_client, _settings(review_threshold=50))
    result = await service.score_candidate(ParsedCv(name="x"), _job())
    assert result.overall_score < 50
    assert result.recommendation == "reject"


@pytest.mark.asyncio
async def test_borderline_candidate_routes_to_review() -> None:
    llm_client = MagicMock()
    llm_client.complete = AsyncMock(
        return_value=MagicMock(
            content=(
                '{"criteria_scores":{"technical_skills":{"score":50,"justification":"x"},'
                '"experience":{"score":50,"justification":"y"}},'
                '"strengths":[],"weaknesses":[],"reasoning":"z","recommendation":"review"}'
            ),
            input_tokens=1,
            output_tokens=1,
            cost_usd=0.0,
            latency_ms=1.0,
            model="gpt-4o",
            prompt_version="cv_scoring_v1",
        )
    )
    service = CandidateScoringService(
        llm_client,
        _settings(shortlist_threshold=80, review_threshold=50),
    )
    result = await service.score_candidate(ParsedCv(name="x"), _job())
    assert result.recommendation == "review"
