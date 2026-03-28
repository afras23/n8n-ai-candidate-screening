"""
CV and attachment parsing (Phase 2).

Extracts machine-readable text from PDF and DOCX payloads.
"""

from __future__ import annotations


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
    raise NotImplementedError("Implemented in Phase 2")
