"""
Integration tests for screening pipeline (Phase 2).

These tests use a real database (skipped if DATABASE_URL is not configured or
Postgres is unreachable) and mock all external integrations + LLM client.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.config import Settings
from app.core.database import async_session_factory
from app.integrations.ats_client import MockAtsClient
from app.integrations.email_client import MockEmailClient
from app.integrations.sheets_client import MockSheetsClient
from app.models.job import JobRequirement
from app.services.matching_service import JobMatchingService
from app.services.parsing_service import CvParsingService
from app.services.scoring_service import CandidateScoringService
from app.services.screening_service import ScreeningService


def _settings() -> Settings:
    return Settings.model_validate(
        {
            "database_url": "postgresql+asyncpg://test:test@127.0.0.1:5432/test_db",
            "openai_api_key": "sk-test",
            "ai_model": "gpt-4o",
            "shortlist_threshold": 80,
            "review_threshold": 50,
        }
    )


@pytest.mark.asyncio
async def test_full_screening_pipeline_shortlist(
    integration_schema_ready: None,
) -> None:
    job_id = uuid.uuid4()
    async with async_session_factory() as session:
        job = JobRequirement(
            id=job_id,
            title="Senior Python Developer",
            description="x",
            requirements_json={
                "must_have": ["Python", "FastAPI"],
                "nice_to_have": ["AWS"],
                "experience_years": 4,
                "education": "Computer Science",
            },
            scoring_rubric_json={
                "technical_skills": {"weight": 1.0, "description": "x"},
            },
            is_active=True,
        )
        session.add(job)
        await session.commit()

    llm_client = MagicMock()
    llm_client.complete = AsyncMock(
        side_effect=[
            MagicMock(
                content=(
                    '{"name":"Jordan","email":"j@example.com","phone":null,'
                    '"location":"Remote","summary":"x","experience":[],'
                    '"education":[],"skills":["Python","FastAPI"],'
                    '"certifications":[],"languages":[]}'
                ),
                input_tokens=5,
                output_tokens=5,
                cost_usd=0.01,
                latency_ms=10.0,
                model="gpt-4o",
                prompt_version="cv_parsing_v1",
            ),
            MagicMock(
                content=(
                    '{"criteria_scores":{"technical_skills":{"score":95,"justification":"ok"}},'
                    '"strengths":["a"],"weaknesses":[],"reasoning":"b","recommendation":"shortlist"}'
                ),
                input_tokens=10,
                output_tokens=10,
                cost_usd=0.02,
                latency_ms=20.0,
                model="gpt-4o",
                prompt_version="cv_scoring_v1",
            ),
        ]
    )

    service = ScreeningService(
        CvParsingService(llm_client),
        CandidateScoringService(llm_client, _settings()),
        JobMatchingService(),
        ats_client=MockAtsClient(),
        sheets_client=MockSheetsClient(),
        email_client=MockEmailClient(),
    )

    async with async_session_factory() as session:
        response = await service.screen_candidate(
            session,
            cv_content=b"# CV text",
            filename="cv.md",
            job_id=job_id,
        )
        await session.commit()

    assert response.recommendation == "shortlist"
    assert response.routed_to == "ats_shortlisted"


@pytest.mark.asyncio
async def test_full_screening_pipeline_reject(
    integration_schema_ready: None,
) -> None:
    job_id = uuid.uuid4()
    async with async_session_factory() as session:
        job = JobRequirement(
            id=job_id,
            title="Senior Python Developer",
            description="x",
            requirements_json={"must_have": ["Python"], "nice_to_have": []},
            scoring_rubric_json={
                "technical_skills": {"weight": 1.0, "description": "x"},
            },
            is_active=True,
        )
        session.add(job)
        await session.commit()

    llm_client = MagicMock()
    llm_client.complete = AsyncMock(
        side_effect=[
            MagicMock(
                content=(
                    '{"name":"Jordan","email":"j@example.com","phone":null,'
                    '"location":"Remote","summary":"x","experience":[],'
                    '"education":[],"skills":["Python"],'
                    '"certifications":[],"languages":[]}'
                ),
                input_tokens=1,
                output_tokens=1,
                cost_usd=0.0,
                latency_ms=1.0,
                model="gpt-4o",
                prompt_version="cv_parsing_v1",
            ),
            MagicMock(
                content=(
                    '{"criteria_scores":{"technical_skills":{"score":10,"justification":"no"}},'
                    '"strengths":[],"weaknesses":["b"],"reasoning":"c","recommendation":"reject"}'
                ),
                input_tokens=1,
                output_tokens=1,
                cost_usd=0.0,
                latency_ms=1.0,
                model="gpt-4o",
                prompt_version="cv_scoring_v1",
            ),
        ]
    )

    service = ScreeningService(
        CvParsingService(llm_client),
        CandidateScoringService(llm_client, _settings()),
        JobMatchingService(),
        ats_client=MockAtsClient(),
        sheets_client=MockSheetsClient(),
        email_client=MockEmailClient(),
    )

    async with async_session_factory() as session:
        response = await service.screen_candidate(
            session,
            cv_content=b"# CV text",
            filename="cv.md",
            job_id=job_id,
        )
        await session.commit()

    assert response.recommendation == "reject"
    assert response.routed_to == "email_rejection"


@pytest.mark.asyncio
async def test_duplicate_cv_skipped(integration_schema_ready: None) -> None:
    job_id = uuid.uuid4()
    cv_bytes = b"# Same CV"

    async with async_session_factory() as session:
        job = JobRequirement(
            id=job_id,
            title="Senior Python Developer",
            description="x",
            requirements_json={"must_have": ["Python"], "nice_to_have": []},
            scoring_rubric_json={
                "technical_skills": {"weight": 1.0, "description": "x"},
            },
            is_active=True,
        )
        session.add(job)
        await session.commit()

    llm_client = MagicMock()
    llm_client.complete = AsyncMock(
        side_effect=[
            MagicMock(
                content=(
                    '{"name":"Jordan","email":"j@example.com","phone":null,'
                    '"location":"Remote","summary":"x","experience":[],'
                    '"education":[],"skills":["Python"],'
                    '"certifications":[],"languages":[]}'
                ),
                input_tokens=1,
                output_tokens=1,
                cost_usd=0.0,
                latency_ms=1.0,
                model="gpt-4o",
                prompt_version="cv_parsing_v1",
            ),
            MagicMock(
                content=(
                    '{"criteria_scores":{"technical_skills":{"score":90,"justification":"ok"}},'
                    '"strengths":[],"weaknesses":[],"reasoning":"c","recommendation":"shortlist"}'
                ),
                input_tokens=1,
                output_tokens=1,
                cost_usd=0.0,
                latency_ms=1.0,
                model="gpt-4o",
                prompt_version="cv_scoring_v1",
            ),
            MagicMock(
                content=(
                    '{"name":"Jordan","email":"j@example.com","phone":null,'
                    '"location":"Remote","summary":"x","experience":[],'
                    '"education":[],"skills":["Python"],'
                    '"certifications":[],"languages":[]}'
                ),
                input_tokens=1,
                output_tokens=1,
                cost_usd=0.0,
                latency_ms=1.0,
                model="gpt-4o",
                prompt_version="cv_parsing_v1",
            ),
        ]
    )

    service = ScreeningService(
        CvParsingService(llm_client),
        CandidateScoringService(llm_client, _settings()),
        JobMatchingService(),
        ats_client=MockAtsClient(),
        sheets_client=MockSheetsClient(),
        email_client=MockEmailClient(),
    )

    async with async_session_factory() as session:
        first = await service.screen_candidate(
            session,
            cv_content=cv_bytes,
            filename="cv.md",
            job_id=job_id,
        )
        await session.commit()

    async with async_session_factory() as session:
        second = await service.screen_candidate(
            session,
            cv_content=cv_bytes,
            filename="cv.md",
            job_id=job_id,
        )
        await session.commit()

    assert first.recommendation in {"shortlist", "review", "reject"}
    assert second.recommendation == "duplicate_skipped"
