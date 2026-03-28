"""
Application exception hierarchy with structured context for APIs and logs.

Each error maps to an HTTP status via handlers in the FastAPI app factory.
"""

from typing import Any


class BaseAppError(Exception):
    """Base error with API-safe fields and optional structured context."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int = 500,
        error_code: str = "INTERNAL_ERROR",
        context: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.context: dict[str, Any] = dict(context) if context else {}
        super().__init__(message)


class ParsingError(BaseAppError):
    """CV or document parsing failed."""

    def __init__(self, message: str, *, context: dict[str, Any] | None = None) -> None:
        super().__init__(
            message,
            status_code=422,
            error_code="PARSING_FAILED",
            context=context,
        )


class ScoringError(BaseAppError):
    """AI scoring failed or produced unusable output."""

    def __init__(self, message: str, *, context: dict[str, Any] | None = None) -> None:
        super().__init__(
            message,
            status_code=502,
            error_code="SCORING_FAILED",
            context=context,
        )


class MatchingError(BaseAppError):
    """Job matching logic failed."""

    def __init__(self, message: str, *, context: dict[str, Any] | None = None) -> None:
        super().__init__(
            message,
            status_code=422,
            error_code="MATCHING_FAILED",
            context=context,
        )


class AtsError(BaseAppError):
    """ATS integration failure."""

    def __init__(self, message: str, *, context: dict[str, Any] | None = None) -> None:
        super().__init__(
            message,
            status_code=502,
            error_code="ATS_ERROR",
            context=context,
        )


class CostLimitExceeded(BaseAppError):
    """Daily or per-request AI cost budget exceeded."""

    def __init__(self, message: str, *, context: dict[str, Any] | None = None) -> None:
        super().__init__(
            message,
            status_code=429,
            error_code="COST_LIMIT_EXCEEDED",
            context=context,
        )


class RetryableError(BaseAppError):
    """Transient upstream failure; safe to retry with backoff."""

    def __init__(self, message: str, *, context: dict[str, Any] | None = None) -> None:
        super().__init__(
            message,
            status_code=503,
            error_code="RETRYABLE_ERROR",
            context=context,
        )


class CircuitBreakerOpenError(BaseAppError):
    """Upstream circuit breaker is open after repeated failures."""

    def __init__(self, message: str, *, context: dict[str, Any] | None = None) -> None:
        super().__init__(
            message,
            status_code=503,
            error_code="CIRCUIT_BREAKER_OPEN",
            context=context,
        )
