"""
Structured JSON logging and correlation ID propagation.

Uses a context variable so log records and HTTP responses share the same id.
"""

from __future__ import annotations

import json
import logging
import sys
from collections.abc import Awaitable, Callable
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.constants import CORRELATION_ID_HEADER

correlation_id_ctx: ContextVar[str | None] = ContextVar(
    "correlation_id",
    default=None,
)


def get_correlation_id() -> str | None:
    """Return the correlation ID for the current async context, if any."""
    return correlation_id_ctx.get()


class CorrelationIdFilter(logging.Filter):
    """Attach correlation_id to log records for the JSON formatter."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_correlation_id()
        return True


class JsonLogFormatter(logging.Formatter):
    """Format log records as single-line JSON."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "correlation_id": getattr(record, "correlation_id", None),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def configure_logging(level_name: str) -> None:
    """Configure root logger for JSON stdout output."""
    level = getattr(logging, level_name.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter())
    handler.addFilter(CorrelationIdFilter())

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    root.addHandler(handler)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Read or generate X-Correlation-ID and store it in a context variable."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        header_value = request.headers.get("x-correlation-id")
        correlation_id = header_value or str(uuid4())
        token: Token[str | None] = correlation_id_ctx.set(correlation_id)
        try:
            response = await call_next(request)
            response.headers[CORRELATION_ID_HEADER] = correlation_id
            return response
        finally:
            correlation_id_ctx.reset(token)
