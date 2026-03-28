"""
OpenAI-backed LLM client with retries, circuit breaking, and cost controls.

All structured log fields use non-reserved ``extra`` keys (avoid ``name``, ``msg``,
``args``, ``levelname``, ``module``, etc.).
"""

from __future__ import annotations

import asyncio
import logging
import random
import time
from collections.abc import Callable
from datetime import UTC, date, datetime

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    RateLimitError,
)
from pydantic import BaseModel, ConfigDict, Field

from app.config import Settings
from app.core.exceptions import CircuitBreakerOpenError, CostLimitExceeded, ScoringError
from app.core.logging_config import get_correlation_id

logger = logging.getLogger(__name__)

MAX_LLM_ATTEMPTS: int = 3
CIRCUIT_FAILURE_THRESHOLD: int = 5
CIRCUIT_OPEN_SECONDS: float = 60.0
BACKOFF_BASE_SECONDS: float = 0.5
BACKOFF_CAP_SECONDS: float = 8.0

COST_PER_MILLION_USD: dict[str, dict[str, float]] = {
    "gpt-4o": {"input": 2.5, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.6},
}
DEFAULT_COST_PER_MILLION: dict[str, float] = {"input": 2.5, "output": 10.0}


class LlmCallResult(BaseModel):
    """Structured result from a single LLM completion call."""

    model_config = ConfigDict(protected_namespaces=(), extra="forbid")

    content: str = Field(..., description="Assistant message text")
    input_tokens: int = Field(..., ge=0)
    output_tokens: int = Field(..., ge=0)
    cost_usd: float = Field(..., ge=0.0)
    latency_ms: float = Field(..., ge=0.0)
    model: str = Field(..., description="Provider model id")
    prompt_version: str = Field(..., description="Logical prompt version label")


def _compute_cost_usd(model_name: str, input_tokens: int, output_tokens: int) -> float:
    rates = COST_PER_MILLION_USD.get(model_name, DEFAULT_COST_PER_MILLION)
    inp = rates["input"]
    out = rates["output"]
    return (input_tokens * inp + output_tokens * out) / 1_000_000


def _is_retryable_error(exc: BaseException) -> bool:
    if isinstance(exc, APIConnectionError | APITimeoutError | RateLimitError):
        return True
    if isinstance(exc, APIStatusError):
        return exc.status_code >= 500
    return False


async def _sleep_backoff(attempt_index: int) -> None:
    raw = min(BACKOFF_BASE_SECONDS * (2**attempt_index), BACKOFF_CAP_SECONDS)
    jitter = random.uniform(0, raw * 0.25)
    await asyncio.sleep(raw + jitter)


class LlmClient:
    """Async OpenAI chat client with observability and guardrails."""

    def __init__(
        self,
        settings: Settings,
        *,
        openai_factory: Callable[[], AsyncOpenAI] | None = None,
    ) -> None:
        self._settings = settings
        self._openai_factory = openai_factory or (
            lambda: AsyncOpenAI(api_key=settings.openai_api_key)
        )
        self._client: AsyncOpenAI | None = None
        self._lock = asyncio.Lock()
        self._daily_total_usd: float = 0.0
        self._cost_day: date = datetime.now(UTC).date()
        self._circuit_failures: int = 0
        self._circuit_open_until_monotonic: float | None = None

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = self._openai_factory()
        return self._client

    def _reset_cost_day_if_needed(self) -> None:
        today = datetime.now(UTC).date()
        if today != self._cost_day:
            self._cost_day = today
            self._daily_total_usd = 0.0

    def _circuit_is_open(self) -> bool:
        if self._circuit_open_until_monotonic is None:
            return False
        if time.monotonic() >= self._circuit_open_until_monotonic:
            self._circuit_open_until_monotonic = None
            return False
        return True

    def _open_circuit(self) -> None:
        self._circuit_open_until_monotonic = time.monotonic() + CIRCUIT_OPEN_SECONDS
        logger.error(
            "llm_circuit_breaker_opened",
            extra={
                "correlation_id": get_correlation_id(),
                "circuit_open_seconds": CIRCUIT_OPEN_SECONDS,
                "consecutive_failures": self._circuit_failures,
            },
        )

    async def _ensure_pre_call_limits(self) -> None:
        async with self._lock:
            self._reset_cost_day_if_needed()
            if self._circuit_is_open():
                raise CircuitBreakerOpenError(
                    "LLM circuit breaker is open",
                    context={"retry_after_hint_seconds": CIRCUIT_OPEN_SECONDS},
                )
            if self._daily_total_usd >= self._settings.max_daily_cost_usd:
                raise CostLimitExceeded(
                    "Daily LLM cost budget exhausted",
                    context={
                        "daily_total_usd": round(self._daily_total_usd, 6),
                        "max_daily_cost_usd": self._settings.max_daily_cost_usd,
                    },
                )

    async def _record_success(self, cost_usd: float) -> float:
        async with self._lock:
            self._circuit_failures = 0
            self._circuit_open_until_monotonic = None
            self._reset_cost_day_if_needed()
            self._daily_total_usd += cost_usd
            return self._daily_total_usd

    async def _record_failure(self) -> None:
        async with self._lock:
            self._circuit_failures += 1
            if self._circuit_failures >= CIRCUIT_FAILURE_THRESHOLD:
                self._open_circuit()

    async def _invoke_openai(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> tuple[str, int, int]:
        client = self._get_client()
        response = await client.chat.completions.create(
            model=self._settings.ai_model,
            max_tokens=self._settings.ai_max_tokens,
            temperature=self._settings.ai_temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        choice = response.choices[0]
        content = choice.message.content or ""
        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0
        return content, input_tokens, output_tokens

    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        prompt_version: str,
    ) -> LlmCallResult:
        """
        Run a chat completion with retries, circuit breaking, and cost accounting.

        Args:
            system_prompt: Model system instructions.
            user_prompt: User / document payload.
            prompt_version: Prompt bundle version label for auditing.

        Returns:
            ``LlmCallResult`` with usage and cost metadata.

        Raises:
            CircuitBreakerOpenError: When the circuit breaker is open.
            CostLimitExceeded: When the daily budget is already exhausted.
            ScoringError: When the provider fails after all retries.
        """
        await self._ensure_pre_call_limits()
        last_error: BaseException | None = None
        started = time.monotonic()

        for attempt in range(MAX_LLM_ATTEMPTS):
            try:
                if attempt > 0:
                    await _sleep_backoff(attempt - 1)
                await self._ensure_pre_call_limits()
                content, input_tokens, output_tokens = await self._invoke_openai(
                    system_prompt,
                    user_prompt,
                )
                latency_ms = (time.monotonic() - started) * 1000
                cost_usd = _compute_cost_usd(
                    self._settings.ai_model,
                    input_tokens,
                    output_tokens,
                )
                daily_after_usd = await self._record_success(cost_usd)
                if cost_usd > self._settings.max_per_cv_cost_usd:
                    logger.warning(
                        "llm_per_cv_cost_above_threshold",
                        extra={
                            "correlation_id": get_correlation_id(),
                            "openai_cost_usd": round(cost_usd, 6),
                            "max_per_cv_cost_usd": self._settings.max_per_cv_cost_usd,
                            "prompt_version_str": prompt_version,
                            "llm_model_id": self._settings.ai_model,
                        },
                    )
                logger.info(
                    "llm_request_completed",
                    extra={
                        "correlation_id": get_correlation_id(),
                        "llm_model_id": self._settings.ai_model,
                        "prompt_version_str": prompt_version,
                        "input_token_count": input_tokens,
                        "output_token_count": output_tokens,
                        "openai_cost_usd": round(cost_usd, 6),
                        "latency_ms_value": round(latency_ms, 2),
                        "daily_total_usd_after": round(daily_after_usd, 6),
                    },
                )
                return LlmCallResult(
                    content=content,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_usd=cost_usd,
                    latency_ms=latency_ms,
                    model=self._settings.ai_model,
                    prompt_version=prompt_version,
                )
            except (CircuitBreakerOpenError, CostLimitExceeded):
                raise
            except BaseException as exc:
                last_error = exc
                if not _is_retryable_error(exc):
                    await self._record_failure()
                    raise ScoringError(
                        "LLM request failed with non-retryable error",
                        context={"error_type": type(exc).__name__},
                    ) from exc
                logger.warning(
                    "llm_request_retryable_error",
                    extra={
                        "correlation_id": get_correlation_id(),
                        "attempt_index": attempt + 1,
                        "max_attempts": MAX_LLM_ATTEMPTS,
                        "error_type": type(exc).__name__,
                    },
                )
                if attempt == MAX_LLM_ATTEMPTS - 1:
                    await self._record_failure()

        assert last_error is not None
        raise ScoringError(
            "LLM request failed after retries",
            context={"error_type": type(last_error).__name__},
        ) from last_error
