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

    # Validate that resume_text is actually readable text (not binary garbage)
    printable_ratio = sum(1 for c in resume_text[:500] if c.isprintable() or c in '\n\r\t') / max(len(resume_text[:500]), 1)
    if printable_ratio < 0.7:
        return ("**Error:** The uploaded resume appears to be corrupted or not a text-based document.\n\n"
                "Please upload a text-based PDF, DOCX, or plain text file.")

    system_prompt = (
        "You are an expert resume writer. Rewrite the provided resume to be perfectly "
        "tailored for the job description below. Follow these strict rules:\n"
        "1. Keep all facts accurate — do NOT invent or fabricate any experience, skills, or qualifications.\n"
        "2. Reorder and emphasize sections that match the job requirements.\n"
        "3. Add relevant keywords from the job description naturally.\n"
        "4. Use clean Markdown formatting with clear section headers (## format).\n"
        "5. Include these sections: Contact Info, Professional Summary, Technical Skills, "
        "Experience, Education, Projects (if relevant).\n"
        "6. Use bullet points with action verbs for experience items.\n"
        "7. Output ONLY the resume content in Markdown — no commentary or explanations."
    )
    
    job_desc = (
        f"Job Title: {job.get('title', 'N/A')}\n"
        f"Company: {job.get('company', 'N/A')}\n"
        f"Location: {job.get('location', 'N/A')}\n"
        f"Requirements: {job.get('description', 'Not provided')}\n"
        f"Required Skills: {job.get('skills', 'Not specified')}"
    )
    
    user_prompt = f"--- Target Job ---\n{job_desc}\n\n--- Original Resume ---\n{resume_text[:8000]}"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    if groq_client is None:
        return "**Error:** No Groq API key configured. Set GROQ_API_KEY_1 in your .env file."

    try:
        response_text = groq_client.chat(messages, temperature=0.3, max_tokens=3000)
        return response_text.strip()
    except Exception as e:
        log.error(f"Resume writer failed: {e}")
        return f"*Error generating tailored resume:* {e}"
