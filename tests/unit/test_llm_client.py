"""
Unit tests for ``LlmClient`` (OpenAI path mocked).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from app.config import Settings
from app.core.exceptions import CostLimitExceeded
from app.services.ai.client import LlmCallResult, LlmClient
from openai import APITimeoutError


def _settings(**overrides: Any) -> Settings:
    data: dict[str, Any] = {
        "database_url": "postgresql+asyncpg://test:test@127.0.0.1:5432/test_db",
        "openai_api_key": "sk-test-key",
        "ai_model": "gpt-4o",
        "ai_max_tokens": 256,
        "ai_temperature": 0.0,
        "max_daily_cost_usd": 50.0,
        "max_per_cv_cost_usd": 2.0,
    }
    data.update(overrides)
    return Settings.model_validate(data)


def _fake_response(content: str, prompt_tokens: int, completion_tokens: int) -> Any:
    class Usage:
        def __init__(self, p: int, c: int) -> None:
            self.prompt_tokens = p
            self.completion_tokens = c

    class Msg:
        def __init__(self, text: str) -> None:
            self.content = text

    class Choice:
        def __init__(self, text: str) -> None:
            self.message = Msg(text)

    class Resp:
        def __init__(self, text: str, p: int, c: int) -> None:
            self.choices = [Choice(text)]
            self.usage = Usage(p, c)

    return Resp(content, prompt_tokens, completion_tokens)


def _client_with_mock_openai(settings: Settings, mock: MagicMock) -> LlmClient:
    return LlmClient(settings, openai_factory=lambda: mock)


@pytest.mark.asyncio
async def test_returns_llm_call_result() -> None:
    """Successful completion returns a populated ``LlmCallResult``."""
    settings = _settings()
    mock = MagicMock()
    mock.chat.completions.create = AsyncMock(
        return_value=_fake_response('{"score": 1}', 10, 20),
    )
    client = _client_with_mock_openai(settings, mock)
    result = await client.complete("sys", "user", prompt_version="unit-v1")
    assert isinstance(result, LlmCallResult)
    assert result.content == '{"score": 1}'
    assert result.input_tokens == 10
    assert result.output_tokens == 20
    assert result.prompt_version == "unit-v1"
    assert result.model == settings.ai_model
    assert result.cost_usd >= 0.0


@pytest.mark.asyncio
async def test_cost_tracking_per_call() -> None:
    """Daily aggregate increases after a successful billed call."""
    settings = _settings(max_daily_cost_usd=100.0)
    mock = MagicMock()
    mock.chat.completions.create = AsyncMock(
        return_value=_fake_response("ok", 100, 100),
    )
    client = _client_with_mock_openai(settings, mock)
    before = client._daily_total_usd
    await client.complete("s", "u", prompt_version="v-cost-1")
    after_first = client._daily_total_usd
    await client.complete("s", "u", prompt_version="v-cost-2")
    after_second = client._daily_total_usd
    assert after_first > before
    assert after_second > after_first


@pytest.mark.asyncio
async def test_daily_cost_limit_enforced() -> None:
    """When the daily cap is already met, the client refuses before calling OpenAI."""
    settings = _settings(max_daily_cost_usd=0.0)
    mock = MagicMock()
    mock.chat.completions.create = AsyncMock(
        return_value=_fake_response("x", 1, 1),
    )
    client = _client_with_mock_openai(settings, mock)
    with pytest.raises(CostLimitExceeded):
        await client.complete("s", "u", prompt_version="v-limit")
    mock.chat.completions.create.assert_not_called()


@pytest.mark.asyncio
async def test_retry_on_timeout_then_success() -> None:
    """Retryable timeouts are retried; a later success returns normally."""
    settings = _settings()
    mock = MagicMock()
    mock.chat.completions.create = AsyncMock(
        side_effect=[
            APITimeoutError("timeout-1"),
            APITimeoutError("timeout-2"),
            _fake_response("recovered", 5, 5),
        ],
    )
    client = _client_with_mock_openai(settings, mock)
    result = await client.complete("s", "u", prompt_version="v-retry")
    assert result.content == "recovered"
    assert mock.chat.completions.create.await_count == 3
