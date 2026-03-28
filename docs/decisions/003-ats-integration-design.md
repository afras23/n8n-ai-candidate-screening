# ADR 003: ATS integration design

## Status

Accepted

## Context

Screening outcomes must flow into an ATS (create/update candidate, status, notes). Real ATS APIs require tenant accounts, OAuth, and vary by vendor.

## Options

1. **Direct ATS API integration** in production from day one
2. **Mock ATS** with realistic CRUD semantics + webhook-style callbacks for demos
3. **File-based export** (CSV) as the only integration

## Decision

Implement a **mock ATS client** with realistic CRUD-style operations (e.g. create candidate, update status, add note) behind a small interface.

## Rationale

- Portfolio and demo environments should run **without** a paid ATS tenancy.
- A mock that mirrors real patterns (ids, errors, retries) demonstrates **how** a production swap would work.
- n8n can still call HTTP nodes against the mock or a stub service; swapping URLs and auth becomes a configuration change.

## Consequences

- **Positive:** Reproducible demos; tests can assert ATS-side effects without external calls.
- **Negative:** Does not prove vendor-specific edge cases until a real integration is built.
- **Mitigation:** Keep the ATS boundary in **integration** code (not in route handlers); document the real integration checklist in the runbook when added.
