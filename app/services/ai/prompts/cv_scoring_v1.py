"""
CV scoring prompt template (version 1).

Used by ``get_prompt("cv_scoring", "v1", ...)``.
"""

SYSTEM_PROMPT = (
    "You are an expert recruiter. Score this CV against the job "
    "requirements. Return ONLY valid JSON with: overall_score (0-100), "
    "criteria_scores (dict of criterion → score 0-100), strengths (list of "
    "strings), weaknesses (list of strings), recommendation "
    "('shortlist'|'review'|'reject')."
)

USER_PROMPT_TEMPLATE = """Job requirements (JSON):
{job_requirements}

CV text:
{cv_text}
"""

VERSION_STRING = "cv_scoring_v1"
