# Operations Runbook — Candidate Screening API

## Health checks

### Liveness

```bash
curl -sS http://localhost:8000/api/v1/health
```

Expect `200` and JSON with `status: healthy` and `timestamp`.

### Readiness (database)

```bash
curl -sS http://localhost:8000/api/v1/health/ready
```

Expect `checks.database: ok` when PostgreSQL is reachable with the configured `DATABASE_URL`. If degraded, verify the DB container, credentials, and network from the app container.

### Metrics

```bash
curl -sS http://localhost:8000/api/v1/metrics
```

Use for: counts screened today, recommendations split, average score/latency, cost today vs `cost_limit_usd`, and `active_jobs`.

## Add a new job with a custom rubric

Rubric and requirements are stored as **JSON** on the `JobRequirement` row (`scoring_rubric_json`, `requirements_json`). You can mirror the shape in `tests/fixtures/sample_inputs/sample_job.json`.

1. **API (recommended)**

```bash
curl -sS -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d @tests/fixtures/sample_inputs/sample_job_api.json
```

The repository also keeps `sample_job.json` (human-readable `requirements` / `scoring_rubric` keys). The API expects `requirements_json` and `scoring_rubric_json` as in `sample_job_api.json`. See `/docs` for the schema.

2. **Verify**

```bash
curl -sS http://localhost:8000/api/v1/jobs
```

## Failed screenings

1. **API errors** — Check application logs (structured JSON) for `correlation_id`, error code, and exception type.
2. **Metrics** — `GET /api/v1/metrics` for volume and cost; spikes in `rejected_today` or zero `avg_score` may indicate parse/score issues.
3. **n8n** — Execution history and failed HTTP nodes; retry policy on the HTTP Request node.
4. **Database** — Ensure migrations applied (`alembic upgrade head`) and `DATABASE_URL` matches the running Postgres.

## Update scoring thresholds

Thresholds are **environment variables** (Pydantic Settings):

- `SHORTLIST_THRESHOLD` (default `80`) — overall score at or above → shortlist recommendation.
- `REVIEW_THRESHOLD` (default `50`) — between review and shortlist band.

Change in `.env`, restart the API container, and re-run a small evaluation (`make evaluate`) or manual tests against a known CV.

## Modify the n8n workflow

1. Import or edit `workflows/candidate_screening.json` in n8n.
2. Update `job_id` in the Extract Attachment Code node (or pass dynamically).
3. Point API URL to your deployment (`API_URL` or full URL on the HTTP Request node).
4. Test with a single email before activating the schedule.

See [n8n-workflow.md](./n8n-workflow.md) for node-by-node notes.

## Common errors and recovery

| Symptom | Likely cause | Recovery |
|--------|----------------|----------|
| `422` on `/screen` — `job_id is required` | Missing form/query `job_id` | Pass `job_id` as form field or `?job_id=` |
| `422` / validation errors | Bad multipart or missing file | Use `-F file=@path` and correct content type |
| `500` Internal error | Unhandled exception in pipeline | Check logs; verify OpenAI key and DB |
| `MatchingError` / job not found | Invalid `job_id` | Create job first; list `/api/v1/jobs` |
| Readiness degraded | DB down or wrong URL | Check Postgres health and `DATABASE_URL` |
| Duplicate CV / duplicate_skipped | Same content hash | Expected; no duplicate rows |
| Cost limit errors | `MAX_DAILY_COST_USD` exceeded | Raise limit or wait for next day |

## Migrations (Docker)

```bash
docker compose exec app alembic upgrade head
```

Ensure `DATABASE_URL` inside the container points at the `db` service (see `docker-compose.yml`).
