# ADR 001: n8n vs pure Python for orchestration

## Status

Accepted

## Context

We need workflow orchestration for email ingestion → CV extraction → AI scoring → conditional routing → ATS, notifications, and analytics. The team wants a production-credible portfolio system without rebuilding low-level integration glue in Python for every channel.

## Options

1. **n8n** — self-hosted workflow engine with triggers, HTTP, email, Sheets, Slack, and branching
2. **Pure Python** — Celery/RQ + FastAPI for all orchestration and integrations
3. **Make.com / Zapier** — SaaS automation

## Decision

Use **n8n** for orchestration and **Python FastAPI** for AI logic (parsing, scoring, matching).

## Rationale

- n8n handles **email triggers**, **conditional routing**, and **third-party integrations** (ATS patterns, email, Sheets, Slack) with a visual, inspectable workflow.
- Python handles what n8n should not own: **CV parsing**, **LLM calls with schema validation**, **cost tracking**, and **testable domain logic**.
- Separation keeps the **AI service reusable** (other clients, not only n8n) and **independently testable** (unit/integration tests without executing full workflows).

## Consequences

- **Positive:** Clear boundary; FastAPI can meet portfolio engineering standards (types, tests, CI) without entangling HTTP handlers with integration adapters.
- **Negative:** Two runtimes to operate (n8n + API); workflow and API contracts must be versioned and documented.
- **Mitigation:** Document request/response schemas and failure branches; use explicit error paths in n8n (retry + alert).
