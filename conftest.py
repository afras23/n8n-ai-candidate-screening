"""
Root pytest configuration: ensure required env exists before ``app`` imports.

Loaded for all tests under this project (pytest walks parent directories).
"""

from __future__ import annotations

import os

os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://test:test@127.0.0.1:5432/test_db",
)
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
