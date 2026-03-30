"""
Integration tests for HTTP endpoints (Phase 3).

These tests override dependencies to avoid external I/O.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

from app.api.routes import candidates as candidates_routes
from app.api.routes import screening as screening_routes
from app.main import app
from fastapi.testclient import TestClient


def test_screen_endpoint_returns_score_and_recommendation() -> None:
    fake_service = MagicMock()
    fake_service.screen_candidate = AsyncMock(
        return_value=MagicMock(
            model_dump=lambda: {
                "candidate_id": str(uuid.uuid4()),
                "candidate_name": "Test User",
                "overall_score": 90,
                "recommendation": "shortlist",
                "match_percentage": 1.0,
                "must_have_missing": [],
                "cost_usd": 0.01,
                "latency_ms": 123.0,
                "routed_to": "ats_shortlisted",
            }
        )
    )

    async def fake_db() -> object:
        yield MagicMock(rollback=AsyncMock())

    app.dependency_overrides[screening_routes.get_screening_service] = (
        lambda: fake_service
    )
    app.dependency_overrides[screening_routes.get_db] = fake_db
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/screen",
            files={"file": ("cv.md", b"# CV", "text/markdown")},
            data={"job_id": str(uuid.uuid4())},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert payload["data"]["recommendation"] == "shortlist"


def test_screen_with_invalid_file_returns_422() -> None:
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/screen",
            files={"file": ("cv.bin", b"\xff\xfe", "application/octet-stream")},
        )
    assert response.status_code == 422


def test_batch_screening_processes_multiple() -> None:
    fake_service = MagicMock()
    fake_service.screen_candidate = AsyncMock(
        side_effect=[
            MagicMock(
                model_dump=lambda: {
                    "candidate_id": str(uuid.uuid4()),
                    "candidate_name": "A",
                    "overall_score": 80,
                    "recommendation": "review",
                    "match_percentage": 0.5,
                    "must_have_missing": ["X"],
                    "cost_usd": 0.01,
                    "latency_ms": 10.0,
                    "routed_to": "ats_review",
                }
            ),
            MagicMock(
                model_dump=lambda: {
                    "candidate_id": str(uuid.uuid4()),
                    "candidate_name": "B",
                    "overall_score": 20,
                    "recommendation": "reject",
                    "match_percentage": 0.0,
                    "must_have_missing": ["Y"],
                    "cost_usd": 0.01,
                    "latency_ms": 10.0,
                    "routed_to": "email_rejection",
                }
            ),
        ]
    )

    async def fake_db() -> object:
        yield MagicMock(rollback=AsyncMock())

    app.dependency_overrides[screening_routes.get_screening_service] = (
        lambda: fake_service
    )
    app.dependency_overrides[screening_routes.get_db] = fake_db
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/screen/batch",
            files=[
                ("files", ("cv1.md", b"# CV1", "text/markdown")),
                ("files", ("cv2.md", b"# CV2", "text/markdown")),
            ],
            data={"job_id": str(uuid.uuid4())},
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
    assert len(payload["data"]["results"]) == 2


def test_candidates_list_paginated() -> None:
    fake_repo = MagicMock()
    fake_repo.list_candidates = AsyncMock(return_value=[])
    fake_repo.count_candidates = AsyncMock(return_value=0)

    async def fake_db() -> object:
        yield MagicMock()

    app.dependency_overrides[candidates_routes.get_candidate_repo] = lambda: fake_repo
    app.dependency_overrides[candidates_routes.get_db] = fake_db
    with TestClient(app) as client:
        response = client.get("/api/v1/candidates?page=1&page_size=10")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "success"
