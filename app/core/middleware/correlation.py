"""
Correlation ID middleware.

This module is the Phase 3 import location for correlation propagation.
"""

from __future__ import annotations

from app.core.logging_config import CorrelationIdMiddleware

__all__ = ["CorrelationIdMiddleware"]
