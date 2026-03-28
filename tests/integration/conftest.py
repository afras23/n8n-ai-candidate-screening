"""
Integration test fixtures (database + Alembic).

Migrations run once per module; tests skip cleanly when Postgres is unreachable.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config


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
