"""
Unit tests for parsing layer (Phase 2).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services.parsing_service import (
    TRUNCATION_MAX_CHARS,
    CvParsingService,
    ParsedCv,
    compute_content_hash,
    parse_file,
)


@pytest.mark.asyncio
async def test_parses_complete_cv() -> None:
    llm_client = MagicMock()
    llm_client.complete = AsyncMock(
        return_value=MagicMock(
            content=(
                '{"name":"Jordan Lee","email":"j@example.com","phone":"1",'
                '"location":"Austin","summary":"x","experience":[],"education":[],'
                '"skills":["Python"],"certifications":[],"languages":[]}'
            ),
            input_tokens=10,
            output_tokens=20,
            cost_usd=0.01,
            latency_ms=12.3,
            model="gpt-4o",
            prompt_version="cv_parsing_v1",
        )
    )
    service = CvParsingService(llm_client)
    parsed = await service.parse_cv("some cv text", "cv.md")
    assert isinstance(parsed, ParsedCv)
    assert parsed.name == "Jordan Lee"
    assert parsed.skills == ["Python"]


@pytest.mark.asyncio
async def test_handles_minimal_cv_gracefully() -> None:
    llm_client = MagicMock()
    llm_client.complete = AsyncMock(
        return_value=MagicMock(
            content='{"name":"","summary":"","experience":[],"education":[],"skills":[],"certifications":[],"languages":[]}',
            input_tokens=1,
            output_tokens=1,
            cost_usd=0.0,
            latency_ms=1.0,
            model="gpt-4o",
            prompt_version="cv_parsing_v1",
        )
    )
    service = CvParsingService(llm_client)
    parsed = await service.parse_cv("x", "cv.txt")
    assert parsed.email is None
    assert parsed.total_experience_years >= 0.0


def test_pdf_text_extraction() -> None:
    mock_pdf = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_text.return_value = "Page 1 text"
    mock_pdf.pages = [mock_page]
    mock_ctx = MagicMock()
    mock_ctx.__enter__.return_value = mock_pdf
    mock_ctx.__exit__.return_value = None

    with patch("pdfplumber.open", return_value=mock_ctx):
        text = parse_file(b"%PDF-1.4", "cv.pdf")
    assert "Page 1 text" in text


def test_content_hash_computed_for_dedup() -> None:
    a = compute_content_hash("Hello\nWorld\n")
    b = compute_content_hash("Hello\nWorld")
    assert a == b


@pytest.mark.asyncio
async def test_very_long_cv_truncated_before_llm() -> None:
    captured: dict[str, str] = {}

    async def complete(
        system_prompt: str,
        user_prompt: str,
        *,
        prompt_version: str,
    ) -> object:
        captured["user_prompt"] = user_prompt
        return MagicMock(
            content='{"name":"","summary":"","experience":[],"education":[],"skills":[],"certifications":[],"languages":[]}',
            input_tokens=1,
            output_tokens=1,
            cost_usd=0.0,
            latency_ms=1.0,
            model="gpt-4o",
            prompt_version=prompt_version,
        )

    llm_client = MagicMock()
    llm_client.complete = AsyncMock(side_effect=complete)
    service = CvParsingService(llm_client)
    long_text = "A" * (TRUNCATION_MAX_CHARS + 10_000)
    await service.parse_cv(long_text, "cv.md")
    assert len(captured["user_prompt"]) < len(long_text)


@pytest.mark.asyncio
async def test_non_english_cv_extracts_what_possible() -> None:
    llm_client = MagicMock()
    llm_client.complete = AsyncMock(
        return_value=MagicMock(
            content=(
                '{"name":"María","email":null,"phone":null,"location":"Madrid",'
                '"summary":"x","experience":[],"education":[],"skills":[],"certifications":[],"languages":["Spanish"]}'
            ),
            input_tokens=1,
            output_tokens=1,
            cost_usd=0.0,
            latency_ms=1.0,
            model="gpt-4o",
            prompt_version="cv_parsing_v1",
        )
    )
    service = CvParsingService(llm_client)
    parsed = await service.parse_cv("Experiencia: ñáéíóú", "cv.txt")
    assert parsed.name == "María"
    assert parsed.location == "Madrid"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("cv_text", "expected_name"),
    [
        ("Name: Jordan Lee\nEmail: j@example.com", "Jordan Lee"),
        ("Jordan Lee", ""),
        ("### CV\n**Name:** Jordan Lee", "Jordan Lee"),
    ],
)
async def test_parse_cv_parametrized_formats(cv_text: str, expected_name: str) -> None:
    llm_client = MagicMock()
    llm_client.complete = AsyncMock(
        return_value=MagicMock(
            content=(
                '{"name":"Jordan Lee","email":"j@example.com","phone":null,'
                '"location":null,"summary":"x","experience":[],"education":[],'
                '"skills":[],"certifications":[],"languages":[]}'
            )
            if expected_name
            else (
                '{"name":"","summary":"","experience":[],"education":[],"skills":[],'
                '"certifications":[],"languages":[]}'
            ),
            input_tokens=1,
            output_tokens=1,
            cost_usd=0.0,
            latency_ms=1.0,
            model="gpt-4o",
            prompt_version="cv_parsing_v1",
        )
    )
    service = CvParsingService(llm_client)
    parsed = await service.parse_cv(cv_text, "cv.md")
    assert parsed.name == expected_name
