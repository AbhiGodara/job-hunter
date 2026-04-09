"""
Agent responsible for tailoring the candidate's resume to match a specific job.
Outputs a targeted resume in clean Markdown format.
"""
import logging
from backend.pipeline.rate_limiter import groq_client

log = logging.getLogger(__name__)

def write_resume(job: dict, resume_text: str) -> str:
    """Rewrites resume into tailored markdown for the specific job."""
    if not job or not resume_text:
        return "Could not generate resume: Missing data."

    system_prompt = (
        "You are an expert resume writer. Rewrite the provided resume to be perfectly "
        "tailored for the job description below. Keep all facts accurate — do not invent "
        "experience. Reorder and emphasize sections that match the job requirements. "
        "Add relevant keywords from the job description naturally. "
        "Output clean Markdown formatted as a professional resume."
    )
    
    job_desc = (
        f"Job Title: {job.get('title')}\n"
        f"Company: {job.get('company')}\n"
        f"Requirements: {job.get('description')}\n"
        f"Required Skills: {job.get('skills')}"
    )
    
    user_prompt = f"--- Target Job ---\n{job_desc}\n\n--- Original Resume ---\n{resume_text[:10000]}"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    try:
        response_text = groq_client.chat(messages, temperature=0.3, max_tokens=3000)
        return response_text.strip()
    except Exception as e:
        log.error(f"Resume writer failed: {e}")
        return f"*Error generating tailored resume:* {e}"
