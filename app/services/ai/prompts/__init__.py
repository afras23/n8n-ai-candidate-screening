"""
Versioned LLM prompt templates and ``get_prompt`` registry.

Concrete templates live in sibling modules (e.g. ``cv_scoring_v1``).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from . import cv_parsing_v1, cv_scoring_v1

PromptBuilder = Callable[..., tuple[str, str, str]]


def _build_cv_scoring(**kwargs: object) -> tuple[str, str, str]:
    job_requirements = str(kwargs.get("job_requirements", ""))
    cv_text = str(kwargs.get("cv_text", ""))
    user = cv_scoring_v1.USER_PROMPT_TEMPLATE.format(
        job_requirements=job_requirements,
        cv_text=cv_text,
    )
    return cv_scoring_v1.SYSTEM_PROMPT, user, cv_scoring_v1.VERSION_STRING


def _build_cv_parsing(**kwargs: object) -> tuple[str, str, str]:
    cv_text = str(kwargs.get("cv_text", ""))
    user = cv_parsing_v1.USER_PROMPT_TEMPLATE.format(cv_text=cv_text)
    return cv_parsing_v1.SYSTEM_PROMPT, user, cv_parsing_v1.VERSION_STRING


_PROMPT_REGISTRY: dict[tuple[str, str], PromptBuilder] = {
    ("cv_scoring", "v1"): _build_cv_scoring,
    ("cv_parsing", "v1"): _build_cv_parsing,
}


def _normalize_version(version: str) -> str:
    cleaned = version.strip().lower()
    if cleaned.startswith("v") and len(cleaned) > 1 and cleaned[1:].isdigit():
        return f"v{cleaned[1:]}"
    if cleaned.isdigit():
        return f"v{cleaned}"
    return cleaned


def get_prompt(name: str, version: str, **kwargs: Any) -> tuple[str, str, str]:
    """
    Resolve a prompt template and format the user message.

    Args:
        name: Logical prompt name (e.g. ``cv_scoring``).
        version: Version label (e.g. ``v1`` or ``1``).
        **kwargs: Template variables for the user prompt.

    Returns:
        Tuple of ``(system_prompt, user_prompt, version_string)``.

    Raises:
        ValueError: If the name/version pair is unknown.
    """
    key = (name.strip().lower(), _normalize_version(version))
    builder = _PROMPT_REGISTRY.get(key)
    if builder is None:
        msg = f"Unknown prompt: {name!r} / {version!r}"
        raise ValueError(msg)
    return builder(**kwargs)


__all__ = ["get_prompt"]
