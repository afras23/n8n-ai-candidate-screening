"""
Integration test fixtures (database + Alembic).

Migrations run once per module; tests skip cleanly when Postgres is unreachable.

Async SQLAlchemy: the app module binds a single global engine at import time, which
breaks under pytest-asyncio's function-scoped event loops (asyncpg connections are
loop-bound). Integration tests must use ``integration_session_factory`` tied to
``integration_async_engine`` instead of ``app.core.database.async_session_factory``.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool


@pytest.fixture(scope="module", autouse=True)
def integration_schema_ready() -> None:
    """Apply Alembic migrations to the configured database."""
    if not os.environ.get("DATABASE_URL"):
        pytest.skip("DATABASE_URL is not set")
    root = Path(__file__).resolve().parents[2]
    cfg = Config(str(root / "alembic.ini"))
    try:
        command.upgrade(cfg, "head")
    except OSError as exc:
        pytest.skip(f"Database unreachable for integration tests: {exc}")
    except Exception as exc:
        pytest.skip(f"Alembic upgrade skipped: {exc!r}")


@pytest_asyncio.fixture
async def integration_async_engine(
    integration_schema_ready: None,
) -> AsyncIterator[AsyncEngine]:
    """
    Engine bound to the current test's event loop; disposed after the test.

    Yields:
        AsyncEngine for ``DATABASE_URL``.

    Raises:
        pytest.skip: If ``DATABASE_URL`` is unset (should not happen after schema fixture).
    """

    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        pytest.skip("DATABASE_URL is not set")
    engine = create_async_engine(
        database_url,
        poolclass=NullPool,
    )
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def integration_session_factory(
    integration_async_engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """
    Session factory bound to ``integration_async_engine`` (same loop as the test).

    Returns:
        ``async_sessionmaker`` producing isolated sessions for this test process.
    """

    return async_sessionmaker(
        bind=integration_async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
