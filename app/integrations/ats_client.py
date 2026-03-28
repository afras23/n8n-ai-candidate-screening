"""
ATS integration protocol and mock implementation.

The mock logs intended operations and returns Pydantic DTOs without network I/O.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AtsCandidateRecord(BaseModel):
    """Response from creating a candidate in the ATS."""

    ats_candidate_id: str = Field(..., description="External ATS primary key")
    candidate_name: str
    candidate_email: str
    job_reference: str
    created_at_utc: datetime


class AtsStatusUpdate(BaseModel):
    """Confirmation of a pipeline status change."""

    ats_candidate_id: str
    new_status: str
    updated_at_utc: datetime


class AtsNote(BaseModel):
    """Confirmation that a note was attached."""

    ats_candidate_id: str
    note_body_preview: str
    note_id: str
    created_at_utc: datetime


@runtime_checkable
class AtsClient(Protocol):
    """Vendor-agnostic ATS operations used by workflows."""

    async def create_candidate(
        self,
        name: str,
        email: str,
        job_id: str,
    ) -> AtsCandidateRecord:
        """Register a new applicant against a job requisition."""

    async def update_status(self, candidate_id: str, status: str) -> AtsStatusUpdate:
        """Move a candidate to a workflow stage."""

    async def add_note(self, candidate_id: str, note: str) -> AtsNote:
        """Attach a recruiter-visible note."""


class MockAtsClient:
    """Mock ATS — logs operations, returns realistic mock data."""

    async def create_candidate(
        self,
        name: str,
        email: str,
        job_id: str,
    ) -> AtsCandidateRecord:
        record_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        logger.info(
            "mock_ats_create_candidate",
            extra={
                "ats_operation": "create_candidate",
                "candidate_name_value": name,
                "candidate_email_value": email,
                "job_reference_id": job_id,
                "ats_candidate_id": record_id,
            },
        )
        return AtsCandidateRecord(
            ats_candidate_id=record_id,
            candidate_name=name,
            candidate_email=email,
            job_reference=job_id,
            created_at_utc=now,
        )

    async def update_status(self, candidate_id: str, status: str) -> AtsStatusUpdate:
        now = datetime.now(UTC)
        logger.info(
            "mock_ats_update_status",
            extra={
                "ats_operation": "update_status",
                "ats_candidate_id": candidate_id,
                "new_status_value": status,
            },
        )
        return AtsStatusUpdate(
            ats_candidate_id=candidate_id,
            new_status=status,
            updated_at_utc=now,
        )

    async def add_note(self, candidate_id: str, note: str) -> AtsNote:
        note_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        preview = note[:200]
        logger.info(
            "mock_ats_add_note",
            extra={
                "ats_operation": "add_note",
                "ats_candidate_id": candidate_id,
                "note_id_value": note_id,
                "note_preview_chars": len(preview),
            },
        )
        return AtsNote(
            ats_candidate_id=candidate_id,
            note_body_preview=preview,
            note_id=note_id,
            created_at_utc=now,
        )
