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

    # Validate that resume_text is actually readable text
    printable_ratio = sum(1 for c in resume_text[:500] if c.isprintable() or c in '\n\r\t') / max(len(resume_text[:500]), 1)
    if printable_ratio < 0.7:
        return ("**Error:** The resume text appears corrupted.\n\n"
                "Please re-upload your resume as a text-based PDF or DOCX file.")

    system_prompt = (
        "You are an expert interview coach. Prepare the candidate for an interview "
        "for the specific role based on their resume.\n\n"
        "Return a comprehensive Markdown guide with EXACTLY these sections:\n\n"
        "## Top 10 Interview Questions & Ideal Answers\n"
        "For each question, provide the question and a tailored answer based on the candidate's resume.\n\n"
        "## 5 Questions to Ask the Interviewer\n"
        "Smart, role-specific questions that show genuine interest.\n\n"
        "## Key Topics to Study\n"
        "Technical concepts, frameworks, and domain knowledge to brush up on.\n\n"
        "## Red Flags to Watch For\n"
        "Warning signs about the role, team, or company to watch during the interview.\n\n"
        "## Salary Negotiation Tips\n"
        "Concrete talking points for negotiating compensation.\n\n"
        "Output ONLY the guide content in clean Markdown — no preamble or commentary."
    )
    
    job_desc = (
        f"Job Title: {job.get('title', 'N/A')}\n"
        f"Company: {job.get('company', 'N/A')}\n"
        f"Location: {job.get('location', 'N/A')}\n"
        f"Requirements: {job.get('description', 'Not provided')}\n"
        f"Skills: {job.get('skills', 'Not specified')}"
    )
    
    user_prompt = f"--- Target Job ---\n{job_desc}\n\n--- Candidate Resume ---\n{resume_text[:8000]}"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    if groq_client is None:
        return "**Error:** No Groq API key configured. Set GROQ_API_KEY_1 in your .env file."

    try:
        return groq_client.chat(messages, temperature=0.4, max_tokens=3000)
    except Exception as e:
        log.error(f"Interview prep failed: {e}")
        return f"*Error generating interview prep:* {e}"
