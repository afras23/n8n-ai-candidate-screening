"""
CV and attachment parsing (Phase 2).

Extracts machine-readable text from PDF and DOCX payloads.
"""

from __future__ import annotations

import hashlib
import importlib
import io
import json
import logging
import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.exceptions import ParsingError
from app.core.logging_config import get_correlation_id
from app.services.ai.client import LlmClient
from app.services.ai.prompts import get_prompt

logger = logging.getLogger(__name__)


class ExperienceEntry(BaseModel):
    """One work experience entry extracted from a CV."""

    model_config = ConfigDict(extra="forbid")

    company: str | None = None
    title: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    duration_months: int | None = Field(default=None, ge=0)
    description: str | None = None


class EducationEntry(BaseModel):
    """One education entry extracted from a CV."""

    model_config = ConfigDict(extra="forbid")

    institution: str | None = None
    degree: str | None = None
    field: str | None = None
    year: int | None = Field(default=None, ge=1900, le=2200)


class ParsedCv(BaseModel):
    """Structured CV representation produced by the parsing layer."""

    model_config = ConfigDict(extra="forbid")

    name: str = ""
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    summary: str = ""
    experience: list[ExperienceEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    total_experience_years: float = Field(default=0.0, ge=0.0)


def compute_content_hash(cv_text: str) -> str:
    """
    Compute a stable content hash for deduplication.

    Args:
        cv_text: Raw text extracted from a CV file.

    Returns:
        Hex-encoded SHA-256 digest of normalized content.
    """

    normalized_text = "\n".join(line.rstrip() for line in cv_text.strip().splitlines())
    return hashlib.sha256(normalized_text.encode("utf-8")).hexdigest()


def _truncate_for_llm(cv_text: str, *, max_chars: int) -> str:
    if len(cv_text) <= max_chars:
        return cv_text
    return cv_text[:max_chars]


_YEAR_RANGE_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
_YEAR_MONTH_RE = re.compile(r"\b(19\d{2}|20\d{2})[-/](0[1-9]|1[0-2])\b")


def _months_from_date_strings(
    start_date: str | None, end_date: str | None
) -> int | None:
    if not start_date:
        return None

    start_year_month = _YEAR_MONTH_RE.search(start_date)
    end_year_month = _YEAR_MONTH_RE.search(end_date or "")
    if start_year_month and end_year_month:
        sy = int(start_year_month.group(1))
        sm = int(start_year_month.group(2))
        ey = int(end_year_month.group(1))
        em = int(end_year_month.group(2))
        months = (ey - sy) * 12 + (em - sm)
        return max(months, 0)

    start_year = _YEAR_RANGE_RE.search(start_date)
    end_year = _YEAR_RANGE_RE.search(end_date or "")
    if start_year and end_year:
        sy = int(start_year.group(1))
        ey = int(end_year.group(1))
        months = (ey - sy) * 12
        return max(months, 0)

    return None


def _calculate_total_experience_years(experiences: list[ExperienceEntry]) -> float:
    total_months = 0
    for entry in experiences:
        if entry.duration_months is not None:
            total_months += entry.duration_months
            continue
        derived = _months_from_date_strings(entry.start_date, entry.end_date)
        if derived is not None:
            total_months += derived
    return round(total_months / 12.0, 2)


def parse_file(file_content: bytes, filename: str) -> str:
    """
    Extract plain text from a CV file payload.

    Args:
        file_content: Raw bytes for the uploaded file.
        filename: The original filename (used for extension inference).

    Returns:
        Extracted plain text.

    Raises:
        ParsingError: When extraction fails or file type is unsupported.
    """

    lower_name = filename.lower()
    if lower_name.endswith(".pdf"):
        try:
            import pdfplumber

            with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                pages_text: list[str] = []
                for page in pdf.pages:
                    pages_text.append(page.extract_text() or "")
                return "\n\n".join(pages_text).strip()
        except (ValueError, OSError) as exc:
            raise ParsingError(
                "Failed to extract text from PDF",
                context={"filename": filename, "error_type": type(exc).__name__},
            ) from exc

    if lower_name.endswith(".docx"):
        try:
            docx_module = importlib.import_module("docx")
            doc = docx_module.Document(io.BytesIO(file_content))
            paragraphs = [p.text for p in doc.paragraphs if p.text]
            return "\n".join(paragraphs).strip()
        except (ValueError, OSError) as exc:
            raise ParsingError(
                "Failed to extract text from DOCX",
                context={"filename": filename, "error_type": type(exc).__name__},
            ) from exc
        except ImportError as exc:
            raise ParsingError(
                "DOCX parsing dependency is not installed",
                context={"filename": filename, "error_type": type(exc).__name__},
            ) from exc

    if lower_name.endswith(".txt") or lower_name.endswith(".md"):
        return file_content.decode("utf-8", errors="replace").strip()

    try:
        return file_content.decode("utf-8", errors="replace").strip()
    except UnicodeError as exc:
        raise ParsingError(
            "Unsupported file encoding",
            context={"filename": filename, "error_type": type(exc).__name__},
        ) from exc


@dataclass(frozen=True)
class _PromptBundle:
    system_prompt: str
    user_prompt: str
    prompt_version: str


def _load_cv_parsing_prompt(cv_text: str) -> _PromptBundle:
    system_prompt, user_prompt, version_string = get_prompt(
        "cv_parsing",
        "v1",
        cv_text=cv_text,
    )
    return _PromptBundle(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        prompt_version=version_string,
    )


def _guess_non_english(cv_text: str) -> bool:
    non_ascii = sum(1 for ch in cv_text[:5000] if ord(ch) > 127)
    return non_ascii > 50


def _parse_llm_json_payload(llm_content: str) -> dict[str, Any]:
    try:
        payload = json.loads(llm_content)
    except json.JSONDecodeError as exc:
        raise ParsingError(
            "LLM returned non-JSON output for CV parsing",
            context={"error_type": type(exc).__name__},
        ) from exc
    if not isinstance(payload, dict):
        raise ParsingError(
            "LLM returned invalid CV parsing payload type",
            context={"payload_type": type(payload).__name__},
        )
    return payload


class CvParsingService:
    """Parse raw CV text into structured data using AI."""

    def __init__(self, llm_client: LlmClient) -> None:
        self._llm_client = llm_client

    async def parse_cv(self, cv_text: str, filename: str) -> ParsedCv:
        """
        Parse raw CV text into structured data using AI.

        Args:
            cv_text: Extracted CV text.
            filename: Source filename for observability.

        Returns:
            Parsed CV structure.

        Raises:
            ParsingError: If LLM output cannot be validated.
        """

        truncated_cv_text = _truncate_for_llm(cv_text, max_chars=48_000)
        prompt = _load_cv_parsing_prompt(truncated_cv_text)
        if _guess_non_english(truncated_cv_text):
            logger.warning(
                "cv_parsing_non_english_hint",
                extra={
                    "correlation_id": get_correlation_id(),
                    "filename_value": filename,
                },
            )

        llm_result = await self._llm_client.complete(
            prompt.system_prompt,
            prompt.user_prompt,
            prompt_version=prompt.prompt_version,
        )

        parsed_payload = _parse_llm_json_payload(llm_result.content)
        try:
            parsed_cv = ParsedCv.model_validate(parsed_payload)
        except ValueError as exc:
            raise ParsingError(
                "LLM returned CV parsing JSON that did not match schema",
                context={"error_type": type(exc).__name__},
            ) from exc

        parsed_cv.total_experience_years = _calculate_total_experience_years(
            parsed_cv.experience
        )
        logger.info(
            "cv_parsing_completed",
            extra={
                "correlation_id": get_correlation_id(),
                "filename_value": filename,
                "llm_model_id": llm_result.model,
                "prompt_version_str": llm_result.prompt_version,
                "input_token_count": llm_result.input_tokens,
                "output_token_count": llm_result.output_tokens,
                "openai_cost_usd": round(llm_result.cost_usd, 6),
                "latency_ms_value": round(llm_result.latency_ms, 2),
                "cv_text_truncated": truncated_cv_text != cv_text,
            },
        )
        return parsed_cv


async def parse_cv_bytes(content: bytes, filename: str) -> str:
    """
    Parse CV file bytes into plain text.

    Args:
        content: Raw file bytes from upload or email attachment.
        filename: Original filename including extension.

    Returns:
        Extracted UTF-8 text suitable for downstream AI scoring.

    Raises:
        NotImplementedError: Until Phase 2 implements parsers.
    """
    return parse_file(content, filename)
