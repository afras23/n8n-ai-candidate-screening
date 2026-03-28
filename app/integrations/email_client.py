"""
Transactional email integration protocol and mock implementation.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class EmailDispatchReceipt(BaseModel):
    """Acknowledgement that a templated message was accepted for delivery."""

    message_id: str
    recipient_address: str
    template_id_value: str
    queued_at_utc: datetime


@runtime_checkable
class EmailClient(Protocol):
    """Vendor-agnostic templated email dispatch."""

    async def send_template(
        self,
        to_address: str,
        template_id: str,
    ) -> EmailDispatchReceipt:
        """Queue a templated email to a recipient."""


class MockEmailClient:
    """Mock email client — logs sends, returns synthetic queue receipt."""

    async def send_template(
        self,
        to_address: str,
        template_id: str,
    ) -> EmailDispatchReceipt:
        message_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        logger.info(
            "mock_email_send_template",
            extra={
                "email_operation": "send_template",
                "recipient_address_value": to_address,
                "template_id_value": template_id,
                "message_id_value": message_id,
            },
        )
        return EmailDispatchReceipt(
            message_id=message_id,
            recipient_address=to_address,
            template_id_value=template_id,
            queued_at_utc=now,
        )
