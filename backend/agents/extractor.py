"""
Agent responsible for parsing raw job listing text into structured JSON.
Uses the rotating Groq client for LLM calls and safely parses responses.
"""
import json
import logging
from backend.pipeline.rate_limiter import groq_client

log = logging.getLogger(__name__)

def extract_job(raw_text: str, url: str, portal: str) -> dict | None:
    """Uses LLM to extract structured JSON from raw scraped text."""
    if not raw_text or len(raw_text.strip()) < 50:
        return None

    system_prompt = (
        "You are a job listing parser. Extract structured data from the following job listing text. "
        "Return ONLY valid JSON with these exact fields: title, company, location, salary, "
        "job_type (full-time/part-time/internship/contract), experience_required, skills (array), "
        "description (max 200 words), url, portal. If a field is not found, use null. "
        "Return nothing except the JSON object."
    )
    
    user_prompt = f"URL: {url}\nPortal: {portal}\n\nJob Listing Text:\n{raw_text[:8000]}"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    try:
        response_text = groq_client.chat(messages, temperature=0.1)
        return _parse_json_safely(response_text, url, portal, raw_text)
    except json.JSONDecodeError:
        log.warning(f"First extraction failed for {url}, retrying with stricter prompt")
        messages[0]["content"] += " CRITICAL: Output ONLY valid JSON starting with { and ending with }. No markdown or backticks."
        try:
            retry_response = groq_client.chat(messages, temperature=0.0)
            return _parse_json_safely(retry_response, url, portal, raw_text)
        except Exception as e:
            log.error(f"Failed to extract JSON on retry for {url}: {e}")
            return None
    except Exception as e:
        log.error(f"LLM extraction error for {url}: {e}")
        return None

def _parse_json_safely(text: str, url: str, portal: str, raw_text: str) -> dict:
    clean_text = text.strip()
    if clean_text.startswith("```json"):
        clean_text = clean_text[7:]
    if clean_text.startswith("```"):
        clean_text = clean_text[3:]
    if clean_text.endswith("```"):
        clean_text = clean_text[:-3]
    clean_text = clean_text.strip()
    
    # Can throw json.JSONDecodeError, to be caught in parent
    data = json.loads(clean_text)
    
    data["url"] = data.get("url") or url
    data["portal"] = data.get("portal") or portal
    data["raw_text"] = raw_text
    return data
