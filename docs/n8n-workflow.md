# n8n Workflow Setup Guide — Candidate Screening

## Overview

This workflow automates candidate CV screening by connecting your email inbox to the AI scoring API. CVs are automatically parsed, scored, routed, and logged.

## Template limits

The file `workflows/candidate_screening.json` is a static export. **Retry policies and HTTP/API failure handling are not embedded**—enable **Retry On Fail**, error workflows, or custom alerting on the **HTTP Request — Call Python API** node (and related nodes) in the n8n UI after import.

In this export, the **Error Handler** code node is connected only from the **false** branch of **IF — Has Attachment?** (emails with no attachment). It does **not** run when the scoring HTTP request fails or the API returns an error status.

## Prerequisites

- n8n instance (cloud or self-hosted)
- Python FastAPI service running (this repo)
- Email account for CV intake
- Google Sheets for logging
- Slack webhook for notifications (optional)

## Importing the Workflow

1. Open n8n
2. Go to Workflows → Import
3. Upload `workflows/candidate_screening.json`
4. Configure credentials (see below)

## Node-by-Node Configuration

### Node 1: Email Trigger

- **Type:** IMAP Email (`emailReadImap`)
- **Credentials:** your intake email (e.g. applications@company.com)
- **Polling interval:** every 5 minutes (or as allowed by your n8n plan)
- **Folder:** INBOX

### Node 2: Has Attachment?

- **Type:** IF
- **Condition:** `{{$json.attachments && $json.attachments.length > 0}}` (matches the exported workflow)

### Node 3: Extract Attachment

- **Type:** Code (JavaScript)
- **Purpose:** Picks the first PDF/DOCX attachment (or first attachment) and passes `job_id`, `fileName`, and binary `data` for the HTTP node.
- **Important:** Replace `JOB_UUID_HERE` in the Code node with a real `JobRequirement` id from your database (or inject it from email metadata if you encode it in the subject line).

### Node 4: Call Scoring API

- **Type:** HTTP Request
- **Method:** POST
- **URL:** `http://your-api-host:8000/api/v1/screen` (or `{{$env.API_URL}}/api/v1/screen` if you set `API_URL` in n8n)
- **Body:** multipart/form-data — binary property mapped to the attachment; `job_id` is passed as a **query** parameter in the template (`?job_id=...`), which the API accepts alongside form upload.
- **Timeout:** 60 seconds (aligned with `executionTimeout` in the workflow JSON)

### Node 5: Route by Score

- **Type:** Switch
- **Routing:** `{{$json.data.recommendation}}` (success responses use the envelope below; scoring fields live under `data`)
- **Branches:** `shortlist`, `review`, `reject`

### Nodes 6a–6c: Actions per route

| Branch | Node name (template) | Action |
|--------|----------------------|--------|
| **shortlist** | HTTP Request — Update ATS (Shortlist) | POST to your ATS (placeholder URL). Body includes `candidate_id` and status. Point URL/credentials at your real ATS or a stub. |
| **review** | HTTP Request — Flag for Review (Slack) | POST to Slack incoming webhook with candidate name and score text. Replace `SLACK_WEBHOOK_URL_PLACEHOLDER`. |
| **reject** | Send Email — Rejection | Sends templated rejection email. Configure SMTP/email credentials and `from`/`to` appropriately. |

All three branches converge on **Google Sheets — Log Result** so every outcome is appended to the sheet.

### Node 7: Log to Google Sheets

- **Type:** Google Sheets
- **Operation:** Append
- **Spreadsheet / range:** Configure `sheetId` and range (template uses `screening_log!A:E`)
- **Columns:** Map from the upstream JSON — typically `candidate_name`, job title, `overall_score`, `recommendation`, and timestamp (align column order with your sheet header row)

### Node 8: Error Handler

- **Type:** Code (in the template) — in the export, only receives the **no attachment** path from **IF — Has Attachment?** (`return [{ json: { error: $json } }];`). Wire follow-up nodes (Slack, HTTP) manually if you want alerts for that case.
- **After import:** On **HTTP Request — Call Python API**, add **Retry On Fail** (e.g. once, ~30s) and error routing or an error workflow for API failures—see **Template limits** above; those settings are not stored in the JSON file.

## Deployment Options

### n8n Cloud

1. Sign up at [https://app.n8n.cloud](https://app.n8n.cloud)
2. Import the workflow from `workflows/candidate_screening.json`
3. Set an environment variable, e.g. `API_URL=https://your-deployed-api.com`, and use it in the HTTP Request URL
4. Configure credentials (IMAP, Google Sheets, Slack, email)
5. Activate the workflow

### Self-Hosted n8n

1. Add n8n to `docker-compose.yml`:

```yaml
      n8n:
        image: n8nio/n8n
        ports:
          - "5678:5678"
        environment:
          - N8N_BASIC_AUTH_ACTIVE=true
          - N8N_BASIC_AUTH_USER=admin
          - N8N_BASIC_AUTH_PASSWORD=changeme
        volumes:
          - n8n_data:/home/node/.n8n
```

2. Start: `docker-compose up -d`
3. Access n8n at `http://localhost:5678`
4. Import the workflow and configure credentials

Ensure the n8n container can reach the API host (`app:8000` works when both services share the same Docker network, as in the template URL).

## API Webhook Format

### Request (what n8n sends)

`POST /api/v1/screen`

`Content-Type: multipart/form-data`

| Field | Description |
|-------|-------------|
| `file` | CV attachment (PDF/DOCX or plain text) |
| `job_id` | UUID of the job to score against (form field **or** query `?job_id=` — both are supported) |

### Response (what n8n receives)

Successful responses use the standard envelope: `status`, `data`, and `metadata`.

```json
{
  "status": "success",
  "data": {
    "candidate_id": "7f9f2b6e-0df1-4c61-bd15-8a5f0b9a55c1",
    "candidate_name": "Jane Smith",
    "overall_score": 85,
    "recommendation": "shortlist",
    "match_percentage": 0.88,
    "must_have_missing": ["AWS"],
    "cost_usd": 0.07,
    "latency_ms": 1234.5,
    "routed_to": "ats_shortlisted"
  },
  "metadata": {
    "correlation_id": "b9b9a6c5-2b03-4ea8-8cc6-9f6a7d40a3f8",
    "timestamp": "2026-03-30T12:00:00.000000+00:00"
  }
}
```

`routed_to` reflects the orchestrator route, for example `ats_shortlisted`, `ats_review`, `email_rejection`, or `skipped_duplicate` for deduplicated CVs.

## Error Handling

These are **operator steps in n8n**, not part of the exported workflow JSON (see **Template limits**):

- If the API returns **500** → configure the HTTP Request node to **retry once** after ~30 seconds
- If retry fails → send a Slack alert to `#recruitment-ops` (or your ops channel)
- If **no attachment** → the template already routes the IF **false** branch to **Error Handler**; extend that branch (e.g. append to Sheets with `no CV found`) if you need visibility

## Monitoring

- **`GET /api/v1/metrics`** — daily screening stats, costs, and aggregates
- **`GET /api/v1/health`** — liveness
- **`GET /api/v1/health/ready`** — readiness (includes database checks when configured)
- **n8n execution history** — per-run status, inputs, and outputs for debugging

## Version

This guide matches the workflow export in `workflows/candidate_screening.json`. Re-import after major API or node changes.
