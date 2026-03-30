"""
Unit tests for parsing layer (Phase 2).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.services.parsing_service import (
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
