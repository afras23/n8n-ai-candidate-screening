# Implementation Plan: n8n + FastAPI Candidate Screening

This plan builds the hybrid system described in `docs/architecture.md` and `docs/problem-definition.md`. All implementation must satisfy the **Definition of Done** in `CLAUDE.md` (types, docstrings, structured logging, Pydantic boundaries, async I/O, specific exceptions, DI, cost tracking for AI, 40+ tests, Docker, CI, Makefile targets, health endpoints, `.env.example`, etc.). **Routes must not contain business logic**; they validate, delegate to services, and format responses.

---

## Phase 1: Python API scaffold + infrastructure + AI client (1–2 hrs)

**Goal:** Runnable FastAPI app with config, logging, dependency wiring, health endpoints, Docker/Makefile/CI skeleton, and an AI client wrapper stub or real provider behind an interface.

### Checklist

- [ ] `app/` layout aligned with portfolio standard (e.g. `api/routes`, `core`, `services`, `config`, `dependencies`)
- [ ] Pydantic Settings + `.env.example` (every variable documented)
- [ ] Structured logging + correlation ID middleware (target)
- [ ] `/api/v1/health`, `/api/v1/health/ready`, `/api/v1/metrics` (ready may degrade without DB until Phase 2)
- [ ] AI client wrapper module with cost/token/latency logging hooks (mock provider acceptable in tests)
- [ ] Dockerfile (multi-stage, non-root, HEALTHCHECK) + `docker-compose` app (+ DB when introduced)
- [ ] `Makefile`: `dev`, `test`, `lint`, `format`, `typecheck`, `docker`, `clean`, `evaluate` (stubs OK if wired in later phase)
- [ ] CI: ruff, ruff format, mypy, pytest with Postgres service where applicable

### Suggested commit message

```
chore: scaffold FastAPI app with config, health endpoints, and AI client shell
```

### Acceptance criteria

- `docker-compose up` starts the API; health endpoint returns 200
- No business logic in route handlers (only wiring)
- Settings load from environment; no secrets in repo
- Definition of Done: **partial** — infrastructure and layering started; full DoD completed in Phase 6

---

## Phase 2: CV parsing + AI scoring + job matching (2–3 hrs)

**Goal:** End-to-end screening pipeline inside the service layer: parse PDF/DOCX → score with rubric-backed structured LLM output → match against job requirements → Pydantic response.

### Checklist

- [ ] CV parser module with explicit failure modes (empty text, unsupported format)
- [ ] Versioned prompts + rubric (YAML or equivalent) loaded from repo, not inline f-strings in services
- [ ] Job matcher uses job requirements from config/DB per `docs/architecture.md`
- [ ] Pydantic models for request/response; validation of LLM JSON before returning
- [ ] Cost limit checks before AI calls; graceful refusal when exceeded
- [ ] Specific exception types + error mapping strategy (for global handler)

### Suggested commit message

```
feat: add CV parsing, rubric-backed AI scoring, and job matching service
```

### Acceptance criteria

- Service-layer function(s) testable without HTTP; parser and scorer unit-tested with mocks
- Image-only / no-text PDF yields a flag for manual processing (no fake score)
- Logs include model, tokens, cost, latency, prompt version (per playbook)

---

## Phase 3: n8n workflow + API endpoints + observability (2–3 hrs)

**Goal:** Stable HTTP contract for n8n; workflow JSON or export documented; observability complete enough to debug production-like runs.

### Checklist

- [ ] Versioned screening endpoint(s) accepting CV payload + job id (multipart or JSON per design)
- [ ] Idempotency or dedupe strategy documented (if email message id passed through)
- [ ] n8n workflow: trigger → extract → POST → branch on score/errors → ATS mock / Slack / Sheets / email paths
- [ ] Error branch: retry policy + alert (webhook or Slack)
- [ ] Request logging with correlation id propagated from n8n header (if provided)

### Suggested commit message

```
feat: expose screening API for n8n and document workflow integration
```

### Acceptance criteria

- n8n can call the API with fixture CV text and receive a validated JSON result
- Failure modes in `docs/problem-definition.md` have a corresponding branch or documented manual queue
- Metrics endpoint exposes cost/utilisation signals aligned with playbook

---

## Phase 4: Expand tests + evaluation pipeline (1–2 hrs)

**Goal:** Test suite and eval artifacts meet portfolio bar; regressions catch rubric/prompt drift.

### Checklist

- [ ] **40+ tests** total (per `CLAUDE.md` Definition of Done — supersedes any lower interim milestone)
- [ ] Unit: parser edge cases, scorer validation failures, matcher, cost limit
- [ ] Integration: API happy path + error paths; mock external AI
- [ ] Security: prompt-injection style inputs; oversize payloads
- [ ] `eval/` or `scripts/evaluate.py` + `make evaluate`; sample inputs under `tests/fixtures/sample_inputs/`
- [ ] Evaluation report format suitable for README (accuracy, pass rate, cost)

### Suggested commit message

```
test: expand coverage and add AI evaluation pipeline
```

### Acceptance criteria

- `make test` passes locally and in CI
- Coverage threshold met if enforced (e.g. ≥80% when configured)
- Evaluation run produces timestamped report under `eval/results/` or equivalent

---

## Phase 5: n8n documentation (1 hr)

**Goal:** Another engineer can reproduce the workflow without guesswork.

### Checklist

- [ ] Document n8n version, import steps, required credentials (env vars), and node list
- [ ] Document HTTP request shape, headers (correlation id), timeouts, retries
- [ ] Document mapping from API response fields to ATS mock / Sheets columns
- [ ] Screenshots or exported workflow attached or linked (no secrets)

### Suggested commit message

```
docs: add n8n workflow setup and integration guide
```

### Acceptance criteria

- New teammate can connect n8n to local API using only repo docs
- Failure branches match `docs/architecture.md` diagram

---

## Phase 6: README + polish + Definition of Done (1 hr)

**Goal:** Portfolio-ready repo: case-study README, architecture pointer, evaluation summary, ADRs linked, full DoD verification.

### Checklist

- [ ] README: problem, solution, architecture (Mermaid), how to run (`docker-compose up`), evaluation highlights
- [ ] `docs/runbook.md` — operations, limits, rollback, common failures
- [ ] `docs/decisions/` indexed from README or `docs/architecture.md`
- [ ] Run full **Definition of Done** checklist from `CLAUDE.md` (code quality, architecture, AI, infra, testing, docs, git hygiene)
- [ ] Remove committed secrets; `.env` never committed; `.gitignore` complete

### Suggested commit message

```
docs: finalize README, runbook, and Definition of Done verification
```

### Acceptance criteria

- Every **mandatory** item in `CLAUDE.md` Definition of Done is checked or explicitly tracked as follow-up (none for portfolio handoff)
- `make lint && make typecheck && make test` pass in CI and locally

---

## Dependency graph (high level)

```text
Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6
                ↑___________________|
         (iterate on API contract if n8n needs changes)
```

## References

- `docs/problem-definition.md` — I/O and success criteria
- `docs/architecture.md` — boundaries and diagrams
- `docs/decisions/` — ADRs 001–003
- `docs/AI-ENGINEERING-PLAYBOOK.md` — implementation discipline
- `docs/PORTFOLIO-ENGINEERING-STANDARD.md` — structure and checklist
