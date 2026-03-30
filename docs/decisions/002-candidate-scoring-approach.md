# ADR 002: Candidate scoring approach

## Status

Accepted

## Context

We must score CVs against job requirements at scale with acceptable consistency and explainability. Pure keyword rules are brittle; unconstrained LLM output is hard to validate and compare across runs.

## Options

1. **Rule-based keyword matching** — fast and cheap, weak on context
2. **LLM-only free-form scoring** — flexible, hard to validate and tune
3. **Hybrid** — LLM scoring constrained by a **structured output** and a **configurable rubric**

## Decision

Use **LLM-based scoring** with **structured output (Pydantic-validated JSON)** and a **configurable rubric** with weighted criteria. In this codebase the rubric is stored as **JSON** on `JobRequirement.scoring_rubric_json` (same logical content as a YAML rubric file, different serialization).

## Rationale

- Rule-based approaches miss context (e.g. “five years in data science” vs “science data entry”).
- LLMs understand narrative CV text but need **explicit constraints**: required JSON shape, per-criterion scores, and rubric weights loaded from configuration (not hardcoded in prompts).
- Structured output enables **regression tests**, **eval pipelines**, and **stable n8n branching** on numeric fields.

## Consequences

- **Positive:** Explainable breakdown per criterion; easier evaluation against recruiter labels; prompt/rubric versioning in repo.
- **Negative:** Ongoing cost and latency governance required; rubric changes need review and re-evaluation.
- **Mitigation:** Per-call and daily cost limits, logging of model/tokens/latency, and a versioned prompt + rubric artifact set.
