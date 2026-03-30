"""
Unit tests for ScreeningService resilience behaviors (Phase 4).
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from app.integrations.ats_client import AtsClient
from app.integrations.email_client import EmailClient
from app.integrations.sheets_client import SheetsClient
from app.models.job import JobRequirement
from app.services.matching_service import MatchResult
from app.services.parsing_service import ParsedCv
from app.services.scoring_service import ScoringResult
from app.services.screening_service import ScreeningService


@pytest.mark.asyncio
async def test_ats_client_unavailable_logs_error_continues() -> None:
    fake_parsing_service = MagicMock()
    fake_parsing_service.parse_cv = AsyncMock(return_value=ParsedCv(name="X"))

    fake_scoring_service = MagicMock()
    fake_scoring_service.score_candidate = AsyncMock(
        return_value=ScoringResult(
            overall_score=90,
            criteria_scores={},
            strengths=[],
            weaknesses=[],
            recommendation="shortlist",
            reasoning="x",
            tokens_used=1,
            cost_usd=0.01,
            latency_ms=1.0,
            prompt_version="cv_scoring_v1",
        )
    )

    fake_matching_service = MagicMock()
    fake_matching_service.match = AsyncMock(
        return_value=MatchResult(
            must_have_matched=[],
            must_have_missing=[],
            nice_to_have_matched=[],
            match_percentage=1.0,
            experience_match=True,
            education_match=True,
        )
    )

    failing_ats: AtsClient = MagicMock()
    failing_ats.update_status = AsyncMock(side_effect=RuntimeError("ATS down"))

    sheets: SheetsClient = MagicMock()
    sheets.append_row = AsyncMock(return_value=MagicMock())

    email: EmailClient = MagicMock()
    email.send_rejection = AsyncMock(return_value=MagicMock())
    email.send_shortlist_notification = AsyncMock(return_value=MagicMock())

    service = ScreeningService(
        fake_parsing_service,
        fake_scoring_service,
        fake_matching_service,
        ats_client=failing_ats,
        sheets_client=sheets,
        email_client=email,
    )

    fake_session = MagicMock()

    job_id = uuid.uuid4()
    fake_job = JobRequirement(
        id=job_id,
        title="Role",
        description="x",
        requirements_json={"must_have": [], "nice_to_have": []},
        scoring_rubric_json={},
        is_active=True,
    )

    with (
        patch("app.services.screening_service.parse_file", return_value="cv text"),
        patch("app.services.screening_service.compute_content_hash", return_value="h"),
        patch("app.services.screening_service.CandidateRepository") as cand_repo_cls,
        patch("app.services.screening_service.JobRepository") as job_repo_cls,
        patch(
            "app.services.screening_service.ScreeningRepository"
        ) as screening_repo_cls,
        patch("app.services.screening_service.logger") as screening_logger,
    ):
        cand_repo = MagicMock()
        cand_repo.get_by_content_hash = AsyncMock(return_value=None)

        async def _create_candidate(candidate: Any) -> Any:
            if getattr(candidate, "id", None) is None:
                candidate.id = uuid.uuid4()
            return candidate

        cand_repo.create = AsyncMock(side_effect=_create_candidate)
        cand_repo_cls.return_value = cand_repo

        job_repo = MagicMock()
        job_repo.get_by_id = AsyncMock(return_value=fake_job)
        job_repo_cls.return_value = job_repo

        screening_repo = MagicMock()
        screening_repo.create = AsyncMock(side_effect=lambda screening: screening)
        screening_repo_cls.return_value = screening_repo

        response = await service.screen_candidate(
            fake_session,
            cv_content=b"file",
            filename="cv.pdf",
            job_id=job_id,
        )

    assert response.recommendation == "shortlist"
    assert any(
        call.args[0] == "ats_update_status_failed"
        and call.kwargs.get("extra", {}).get("error_type") == "RuntimeError"
        for call in screening_logger.error.call_args_list
    )


@pytest.mark.asyncio
async def test_sheets_client_failure_doesnt_block_screening() -> None:
    fake_parsing_service = MagicMock()
    fake_parsing_service.parse_cv = AsyncMock(return_value=ParsedCv(name="X"))

    fake_scoring_service = MagicMock()
    fake_scoring_service.score_candidate = AsyncMock(
        return_value=ScoringResult(
            overall_score=10,
            criteria_scores={},
            strengths=[],
            weaknesses=[],
            recommendation="reject",
            reasoning="x",
            tokens_used=1,
            cost_usd=0.0,
            latency_ms=1.0,
            prompt_version="cv_scoring_v1",
        )
    )

    fake_matching_service = MagicMock()
    fake_matching_service.match = AsyncMock(
        return_value=MatchResult(
            must_have_matched=[],
            must_have_missing=[],
            nice_to_have_matched=[],
            match_percentage=0.0,
            experience_match=False,
            education_match=False,
        )
    )

    ats: AtsClient = MagicMock()
    ats.update_status = AsyncMock(return_value=MagicMock())

    failing_sheets: SheetsClient = MagicMock()
    failing_sheets.append_row = AsyncMock(side_effect=RuntimeError("Sheets down"))

    email: EmailClient = MagicMock()
    email.send_rejection = AsyncMock(return_value=MagicMock())
    email.send_shortlist_notification = AsyncMock(return_value=MagicMock())

    service = ScreeningService(
        fake_parsing_service,
        fake_scoring_service,
        fake_matching_service,
        ats_client=ats,
        sheets_client=failing_sheets,
        email_client=email,
    )

    fake_session = MagicMock()
    job_id = uuid.uuid4()
    fake_job = JobRequirement(
        id=job_id,
        title="Role",
        description="x",
        requirements_json={"must_have": [], "nice_to_have": []},
        scoring_rubric_json={},
        is_active=True,
    )

    with (
        patch("app.services.screening_service.parse_file", return_value="cv text"),
        patch("app.services.screening_service.compute_content_hash", return_value="h"),
        patch("app.services.screening_service.CandidateRepository") as cand_repo_cls,
        patch("app.services.screening_service.JobRepository") as job_repo_cls,
        patch(
            "app.services.screening_service.ScreeningRepository"
        ) as screening_repo_cls,
        patch("app.services.screening_service.logger") as screening_logger,
    ):
        cand_repo = MagicMock()
        cand_repo.get_by_content_hash = AsyncMock(return_value=None)

        async def _create_candidate(candidate: Any) -> Any:
            if getattr(candidate, "id", None) is None:
                candidate.id = uuid.uuid4()
            return candidate

        cand_repo.create = AsyncMock(side_effect=_create_candidate)
        cand_repo_cls.return_value = cand_repo

        job_repo = MagicMock()
        job_repo.get_by_id = AsyncMock(return_value=fake_job)
        job_repo_cls.return_value = job_repo

        screening_repo = MagicMock()
        screening_repo.create = AsyncMock(side_effect=lambda screening: screening)
        screening_repo_cls.return_value = screening_repo

        response = await service.screen_candidate(
            fake_session,
            cv_content=b"file",
            filename="cv.pdf",
            job_id=job_id,
        )

    assert response.recommendation == "reject"
    assert any(
        call.args[0] == "sheets_append_row_failed"
        and call.kwargs.get("extra", {}).get("error_type") == "RuntimeError"
        for call in screening_logger.error.call_args_list
    )
