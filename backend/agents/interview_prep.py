"""
Agent responsible for creating a strategic interview preparation guide.
"""
import logging
from backend.pipeline.rate_limiter import groq_client

log = logging.getLogger(__name__)

def prep_interview(job: dict, resume_text: str) -> str:
    """Generates a complete interview strategy guide in Markdown format."""
    if not job or not resume_text:
        return "Could not generate interview prep: missing data."

    system_prompt = (
        "You are an expert interview coach. Your goal is to prepare the candidate for an interview "
        "for the specific role based on their resume. Return a Markdown guide with exactly these sections:\n"
        "1. Top 10 likely interview questions with ideal answers tailored to this specific job\n"
        "2. 5 questions the candidate should ask the interviewer\n"
        "3. Key topics to study before the interview\n"
        "4. Red flags to watch for in this role\n"
        "5. Salary negotiation talking points"
    )
    
    job_desc = (
        f"Job Title: {job.get('title')}\n"
        f"Company: {job.get('company')}\n"
        f"Requirements: {job.get('description')}\n"
        f"Skills: {job.get('skills')}"
    )
    
    user_prompt = f"--- Target Job ---\n{job_desc}\n\n--- Candidate Resume ---\n{resume_text[:10000]}"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    try:
        return groq_client.chat(messages, temperature=0.4, max_tokens=3000)
    except Exception as e:
        log.error(f"Interview prep failed: {e}")
        return f"*Error generating interview prep:* {e}"
