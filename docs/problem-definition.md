# Problem Definition: n8n + AI Candidate Screening

## Business Context

Mid-size recruitment agency (10–30 staff) handling 200+ candidate applications per week across 15–25 open roles. Applications arrive via email (CV attachments), job board integrations, and direct submissions.

## Current Manual Process

1. Recruiter opens email with CV attachment (~2 min)
2. Downloads and reads CV — scans for relevant experience, skills, education (~5–8 min per CV)
3. Opens the relevant job description in their ATS
4. Mentally scores the candidate against requirements (~2 min)
5. Decides: shortlist, reject, or “maybe” pile (~1 min)
6. If shortlisted: updates ATS record, moves to next stage (~2 min)
7. If rejected: sends rejection email (~1 min, often skipped)
8. Logs outcome in Google Sheet tracker (~1 min)

**Total:** approximately 12–15 minutes per application × 200/week ≈ **40–50 hours/week** of recruiter time spent on initial screening.

## Pain Points

- **Volume:** 200+ CVs/week is overwhelming for a small team
- **Consistency:** different recruiters score differently
- **Speed:** candidates wait days for initial response and lose interest
- **Missed matches:** good candidates rejected because a recruiter was tired or rushed
- **No data:** no systematic scoring means no disciplined way to improve the process
- **Rejection emails:** often not sent, damaging employer brand

## What the System Does

n8n workflow automates the pipeline:

1. Email arrives with CV attachment → n8n triggers
2. n8n extracts the attachment
3. n8n calls the Python FastAPI service with CV content + job ID
4. Python service: parses CV → AI scores candidate → matches against job
5. n8n receives score and recommendation
6. n8n routes based on score:
   - **High score (≥80):** auto-shortlist → update ATS → notify recruiter
   - **Medium score (50–79):** flag for manual review → notify recruiter
   - **Low score (<50):** auto-reject → send rejection email → log
7. All outcomes logged to Google Sheets for analytics

## Inputs

- Email with CV attachment (PDF, DOCX)
- Job ID or job title to match against
- Job requirements (stored in config or ATS)

## Outputs

- Candidate score (0–100) with breakdown
- Match assessment against specific job requirements
- Routing decision (shortlist / review / reject)
- ATS record update
- Candidate notification email
- Google Sheets log entry

## Failure Modes

- **CV is image-only PDF** (no extractable text) → flag for manual processing
- **AI service is down** → n8n error branch → queue for retry + alert
- **ATS API unavailable** → log locally, retry later
- **Email has no attachment** → skip, log as “no CV”
- **CV is in unsupported format** → flag for manual processing
- **AI score is borderline** → route to manual review; never auto-reject on uncertainty alone

## Success Criteria

- Process 200+ CVs/week with **<5 minutes** human involvement per batch (exceptions: manual-review queue, parse failures)
- **Scoring consistency:** same CV scores within **±5 points** across runs (same model, prompt version, and rubric)
- **Accuracy:** **>80%** agreement with recruiter decisions on a held-out test set
- **Response time:** candidate gets acknowledgement within **1 hour**
- **Zero missed CVs:** every email processed or explicitly flagged
- **Cost per CV:** **<$0.10** for AI processing (tracked per request and daily aggregate)
