"""
Transactional email integration protocol and mock implementation.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable
from uuid import uuid5

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class EmailDispatchReceipt(BaseModel):
    """Acknowledgement that a message would be queued for delivery."""

    message_id: str
    recipient_address: str
    email_type: str
    queued_at_utc: datetime


@runtime_checkable
class EmailClient(Protocol):
    """Vendor-agnostic email notifications used by workflows."""

    async def send_rejection(
        self,
        candidate_email: str,
        candidate_name: str,
        job_title: str,
    ) -> EmailDispatchReceipt:
        """Queue a rejection email to a candidate."""

    async def send_shortlist_notification(
        self,
        recruiter_email: str,
        candidate_name: str,
        score: int,
    ) -> EmailDispatchReceipt:
        """Notify recruiter that a candidate was shortlisted."""


class MockEmailClient:
    """Mock email client — logs sends, returns synthetic queue receipt."""

    async def send_rejection(
        self,
        candidate_email: str,
        candidate_name: str,
        job_title: str,
    ) -> EmailDispatchReceipt:
        message_id = str(
            uuid5(
                uuid.NAMESPACE_URL,
                f"email:rejection:{candidate_email}:{candidate_name}:{job_title}",
            )
        )
        now = datetime.now(UTC)
        logger.info(
            "mock_email_send_rejection",
            extra={
                "email_operation": "send_rejection",
                "recipient_address_value": candidate_email,
                "candidate_name_value": candidate_name,
                "job_title_value": job_title,
                "message_id_value": message_id,
            },
        )
        return EmailDispatchReceipt(
            message_id=message_id,
            recipient_address=candidate_email,
            email_type="rejection",
            queued_at_utc=now,
        )

    async def send_shortlist_notification(
        self,
        recruiter_email: str,
        candidate_name: str,
        score: int,
    ) -> EmailDispatchReceipt:
        message_id = str(
            uuid5(
                uuid.NAMESPACE_URL,
                f"email:shortlist:{recruiter_email}:{candidate_name}:{score}",
            )
        )
        now = datetime.now(UTC)
        logger.info(
            "mock_email_send_shortlist_notification",
            extra={
                "email_operation": "send_shortlist_notification",
                "recipient_address_value": recruiter_email,
                "candidate_name_value": candidate_name,
                "overall_score_value": score,
                "message_id_value": message_id,
            },
        )
        return EmailDispatchReceipt(
            message_id=message_id,
            recipient_address=recruiter_email,
            email_type="shortlist_notification",
            queued_at_utc=now,
        )
