"""
Google Sheets integration protocol and mock implementation.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class SheetsAppendReceipt(BaseModel):
    """Acknowledgement of an appended spreadsheet row."""

    spreadsheet_id: str
    sheet_tab_name: str
    row_number: int
    append_id: str
    recorded_at_utc: datetime


@runtime_checkable
class SheetsClient(Protocol):
    """Vendor-agnostic append-only logging to a spreadsheet."""

    async def append_row(self, row: dict[str, str]) -> SheetsAppendReceipt:
        """Append one structured row for analytics."""


class MockSheetsClient:
    """Mock Sheets client — logs payloads, returns synthetic receipt."""

    def __init__(
        self,
        spreadsheet_id: str = "mock-spreadsheet",
        tab_name: str = "screening_log",
    ) -> None:
        self._spreadsheet_id = spreadsheet_id
        self._tab_name = tab_name
        self._next_row = 2

    async def append_row(self, row: dict[str, str]) -> SheetsAppendReceipt:
        append_id = str(uuid.uuid4())
        now = datetime.now(UTC)
        row_number = self._next_row
        self._next_row += 1
        logger.info(
            "mock_sheets_append_row",
            extra={
                "sheets_operation": "append_row",
                "spreadsheet_id_value": self._spreadsheet_id,
                "sheet_tab_name": self._tab_name,
                "row_number_value": row_number,
                "append_id_value": append_id,
                "row_key_count": len(row),
            },
        )
        return SheetsAppendReceipt(
            spreadsheet_id=self._spreadsheet_id,
            sheet_tab_name=self._tab_name,
            row_number=row_number,
            append_id=append_id,
            recorded_at_utc=now,
        )
