"""
Declarative base for SQLAlchemy models.

Concrete tables are defined in sibling modules.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared metadata registry for all ORM models."""
