"""
CV parsing prompt template (version 1).

Used by ``get_prompt("cv_parsing", "v1", ...)``.
"""

SYSTEM_PROMPT = (
    "Extract structured information from this CV. Return ONLY valid JSON with: "
    "name, email, phone, location, summary, experience (list of {company, "
    "title, start_date, end_date, description}), education (list of "
    "{institution, degree, field, year}), skills (list of strings), "
    "certifications (list), languages (list)."
)

USER_PROMPT_TEMPLATE = """CV text:
{cv_text}
"""

VERSION_STRING = "cv_parsing_v1"
