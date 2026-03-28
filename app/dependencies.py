"""
FastAPI dependency injection wiring.

Import ``get_db`` from here in routes so session creation stays centralized.
"""

from app.core.database import get_db

__all__ = ["get_db"]
