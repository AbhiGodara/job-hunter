"""
Agent responsible for researching the company and its culture.
Performs web search to augment LLM's knowledge.
"""
import logging
from backend.pipeline.rate_limiter import groq_client

log = logging.getLogger(__name__)

def _search_web(query: str, max_results: int = 5) -> list:
    """Search the web for company info using DuckDuckGo."""
    try:
        from ddgs import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            return [
                {"title": r.get("title", ""), "snippet": r.get("body", "")}
                for r in results
            ]
    except Exception as e:
        log.warning(f"Web search failed: {e}")
        return []


def research_company(job: dict) -> str:
    """Generates a company research report based on web search and LLM knowledge."""
    if not job:
        return "Missing job data."
        
    company = job.get("company", "Unknown Company")
    title = job.get("title", "Unknown Role")
    
    # Try web search to augment knowledge
    search_context = ""
    try:
        query = f"{company} {title} tech stack culture news interview process"
        results = _search_web(query, max_results=5)
        if results:
            search_context = "\n".join(f"- {r.get('title')}: {r.get('snippet')}" for r in results)
    except Exception as e:
        log.warning(f"Web search failed during company research: {e}")

    system_prompt = (
        "You are an expert career researcher."
        "Generate a Markdown report with exactly these sections: "
        "Company Overview, Tech Stack, Recent News, Interview Process, "
        "Culture & Work-Life Balance, Why This Role Is Interesting. "
        "If web search context is empty or unhelpful, rely on your existing knowledge "
        "and mention any limitations."
    )
    
    user_prompt = f"Company: {company}\nRole: {title}\n\n"
    if search_context:
        user_prompt += f"--- Web Search Context ---\n{search_context}\n\n"
        
    user_prompt += "Please create the comprehensive research report in Markdown."
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    try:
        return groq_client.chat(messages, temperature=0.3, max_tokens=2500)
    except Exception as e:
        log.error(f"Researcher failed: {e}")
        return f"*Error generating research report:* {e}"
