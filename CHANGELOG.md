# Changelog

All notable changes to this project are described by implementation phase.

## Phase 1 — Python API scaffold, infrastructure, AI client

- FastAPI app scaffold, Pydantic Settings, structured logging, correlation ID middleware.
- Health endpoints: `/api/v1/health`, `/api/v1/health/ready`, `/api/v1/metrics`.
- `LlmClient` with retries, circuit breaker, cost tracking, and structured logging.
- SQLAlchemy models (`Candidate`, `ScreeningResult`, `JobRequirement`), Alembic async migrations.
- Integration mocks (ATS, Sheets, Email) with protocols and deterministic behavior.
- Docker multi-stage image, `docker-compose` with Postgres, Makefile, CI (ruff, mypy, pytest).

## Phase 2 — CV parsing, AI scoring, job matching

- `CvParsingService` with PDF/DOCX/text extraction, truncation, `ParsedCv` models.
- `CandidateScoringService` with rubric-backed LLM output, weighted score, threshold routing.
- `JobMatchingService` deterministic must-have / experience matching.
- Repositories for candidates, jobs, screening; `ScreeningService.screen_candidate` orchestration pipeline.

## Phase 3 — n8n workflow, API, observability

- Screening routes: `POST /api/v1/screen`, batch screen, candidates, jobs; `SuccessEnvelope` / `ErrorEnvelope`.
- `workflows/candidate_screening.json` importable n8n template.
- Request logging middleware; metrics endpoint backed by database aggregates.

## Phase 4 — Tests and evaluation

- Expanded unit tests (parsing, scoring, matching, resilience, security, LLM client).
- `eval/test_set.jsonl`, `scripts/evaluate.py`, `make evaluate`, reports under `eval/results/`.

## Phase 5 — n8n documentation

- `docs/n8n-workflow.md` (import, nodes, API contract, deployment).

## Phase 6 — README, runbook, polish, Definition of Done

- Case-study README, `docs/runbook.md`, `CHANGELOG.md`, evaluation summary and architecture references.
- DoD verification documented in README.
- `python-multipart` added for `multipart/form-data` file uploads; `docker-compose` default `OPENAI_API_KEY` for container boot; job routes serialize UUIDs with `model_dump(mode="json")`.
