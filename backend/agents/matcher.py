"""
Agent responsible for scoring extracted jobs against the candidate's resume.
Returns a score (1-5) and a short evaluation reason.
"""
import json
import logging
from backend.pipeline.rate_limiter import groq_client

log = logging.getLogger(__name__)

def match_job(job: dict, resume_text: str) -> tuple[int, str]:
    """
    Scores the job match from 1 to 5 based on applicant's resume.
    Returns: (score, reason)
    """
    if not job or not resume_text:
        return 2, "Could not evaluate: missing job or resume data"

    system_prompt = (
        "You are a career counselor. Score this job against the candidate's resume on a scale of 1-5 where: "
        "5=perfect match (80%+ skills match, right experience level), "
        "4=strong match (60%+ skills match), "
        "3=decent match (40%+ skills match, worth applying), "
        "2=weak match (possible stretch goal), "
        "1=poor match (don't apply). "
        "Return ONLY valid JSON: {\"score\": integer 1-5, \"reason\": \"string max 80 words\", "
        "\"missing_skills\": [array of strings], \"matching_skills\": [array of strings]}"
    )
    
    # We serialize job details for the LLM
    job_str = (
        f"Title: {job.get('title')}\n"
        f"Company: {job.get('company')}\n"
        f"Description: {job.get('description')}\n"
        f"Skills Required: {job.get('skills')}\n"
        f"Experience Required: {job.get('experience_required')}"
    )
    
    user_prompt = f"--- Job Role ---\n{job_str}\n\n--- Candidate Resume ---\n{resume_text[:10000]}"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    try:
        response_text = groq_client.chat(messages, temperature=0.1)
        clean_text = response_text.strip()
        if clean_text.startswith("```json"):
            clean_text = clean_text[7:]
        if clean_text.startswith("```"):
            clean_text = clean_text[3:]
        if clean_text.endswith("```"):
            clean_text = clean_text[:-3]
        clean_text = clean_text.strip()
        
        data = json.loads(clean_text)
        
        score = int(data.get("score", 2))
        reason = str(data.get("reason", "Could not evaluate"))
        
        if score < 1: score = 1
        if score > 5: score = 5
        
        return score, reason
    except Exception as e:
        log.warning(f"Matcher failed for job {job.get('title')}: {e}")
        return 2, "Could not evaluate due to processing error"
