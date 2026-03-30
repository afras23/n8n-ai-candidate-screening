"""
Unit tests for deterministic matching service (Phase 2).
"""

from __future__ import annotations

import pytest
from app.models.job import JobRequirement
from app.services.matching_service import JobMatchingService
from app.services.parsing_service import EducationEntry, ExperienceEntry, ParsedCv


def _job(requirements: dict[str, object]) -> JobRequirement:
    return JobRequirement(
        title="Role",
        description="x",
        requirements_json=requirements,
        scoring_rubric_json={},
        is_active=True,
    )


@pytest.mark.asyncio
async def test_all_must_haves_matched() -> None:
    service = JobMatchingService()
    parsed = ParsedCv(
        name="x",
        skills=["Python", "FastAPI", "PostgreSQL", "REST APIs"],
        summary="",
        experience=[],
        education=[],
        certifications=[],
        languages=[],
        total_experience_years=5.0,
    )
    job = _job({"must_have": ["Python", "FastAPI"]})
    match = await service.match(parsed, job)
    assert match.must_have_missing == []
    assert match.match_percentage == 1.0


@pytest.mark.asyncio
async def test_missing_must_haves_identified() -> None:
    service = JobMatchingService()
    parsed = ParsedCv(
        name="x",
        skills=["Python"],
        summary="",
        experience=[],
        education=[],
        certifications=[],
        languages=[],
        total_experience_years=1.0,
    )
    job = _job({"must_have": ["Python", "PostgreSQL"]})
    match = await service.match(parsed, job)
    assert "PostgreSQL" in match.must_have_missing


@pytest.mark.asyncio
async def test_match_percentage_calculated() -> None:
    service = JobMatchingService()
    parsed = ParsedCv(
        name="x",
        skills=["Python"],
        summary="",
        experience=[],
        education=[],
        certifications=[],
        languages=[],
        total_experience_years=1.0,
    )
    job = _job({"must_have": ["Python", "FastAPI", "PostgreSQL", "REST APIs"]})
    match = await service.match(parsed, job)
    assert match.match_percentage == 0.25


@pytest.mark.asyncio
async def test_experience_years_check() -> None:
    service = JobMatchingService()
    parsed = ParsedCv(
        name="x",
        skills=["Python"],
        summary="",
        experience=[ExperienceEntry(company="a", title="b", description="c")],
        education=[EducationEntry(institution="u", degree="BS", field="CS", year=2019)],
        certifications=[],
        languages=[],
        total_experience_years=3.9,
    )
    job = _job({"experience_years": 4})
    match = await service.match(parsed, job)
    assert match.experience_match is False


@pytest.mark.asyncio
async def test_partial_skill_match_calculated_correctly() -> None:
    service = JobMatchingService()
    parsed = ParsedCv(
        name="x",
        skills=["Python", "FastAPI"],
        summary="",
        experience=[],
        education=[],
        certifications=[],
        languages=[],
        total_experience_years=5.0,
    )
    job = _job({"must_have": ["Python", "FastAPI", "PostgreSQL", "REST APIs"]})
    match = await service.match(parsed, job)
    assert match.match_percentage == 0.5


@pytest.mark.asyncio
async def test_experience_slightly_below_requirement() -> None:
    service = JobMatchingService()
    parsed = ParsedCv(
        name="x",
        skills=["Python"],
        summary="",
        experience=[],
        education=[],
        certifications=[],
        languages=[],
        total_experience_years=3.99,
    )
    job = _job({"experience_years": 4})
    match = await service.match(parsed, job)
    assert match.experience_match is False
