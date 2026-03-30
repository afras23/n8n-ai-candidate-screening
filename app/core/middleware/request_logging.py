"""
Request logging middleware.

Logs method, path, status code, latency, and correlation id.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging_config import get_correlation_id

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log one structured entry per HTTP request."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        started = time.monotonic()
        response = await call_next(request)
        latency_ms = (time.monotonic() - started) * 1000

        extra = {
            "correlation_id": get_correlation_id(),
            "http_method": request.method,
            "http_path": request.url.path,
            "http_status_code": response.status_code,
            "latency_ms_value": round(latency_ms, 2),
        }

        if 200 <= response.status_code < 400:
            logger.info("http_request_completed", extra=extra)
        elif 400 <= response.status_code < 500:
            logger.warning("http_request_completed", extra=extra)
        else:
            logger.error("http_request_completed", extra=extra)

        return response


__all__ = ["RequestLoggingMiddleware"]
