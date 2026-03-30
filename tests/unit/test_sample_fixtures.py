"""
Contract checks for committed sample inputs (Phase 6 / demoability).
"""

from __future__ import annotations

import json
from pathlib import Path

_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "sample_inputs"


def test_sample_job_json_has_rubric_and_requirements() -> None:
    """Sample job fixture must include requirements and scoring rubric keys."""
    path = _FIXTURES / "sample_job.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert "requirements" in payload
    assert "scoring_rubric" in payload
    assert isinstance(payload["requirements"], dict)
    assert isinstance(payload["scoring_rubric"], dict)


def test_sample_cv_markdown_is_non_empty() -> None:
    """Sample CV text fixture must exist for local demos and curl examples."""
    path = _FIXTURES / "sample_cv.md"
    text = path.read_text(encoding="utf-8")
    assert len(text.strip()) >= 20
