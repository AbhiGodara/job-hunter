"""
Deduplicates job postings by normalized URL and company+title pairs.
Strips query parameters and trailing slashes from URLs.
"""
from urllib.parse import urlparse, urlunparse

def deduplicate_jobs(jobs: list[dict]) -> list[dict]:
    """Returns unique job postings by normalizing URLs and checking metadata."""
    unique_jobs = []
    seen_urls = set()
    seen_company_titles = set()
    
    for job in jobs:
        url = job.get("url", "")
        company = str(job.get("company", "")).strip().lower()
        title = str(job.get("title", "")).strip().lower()
        
        # Normalize URL: Strip query params and fragments, remove trailing slash
        if url:
            parsed = urlparse(url)
            normalized_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", "")).rstrip("/")
            job["url"] = normalized_url
        else:
            normalized_url = ""
            
        is_duplicate = False
        
        if normalized_url and normalized_url in seen_urls:
            is_duplicate = True
            
        if company and title:
            combo = f"{company}::{title}"
            if combo in seen_company_titles:
                is_duplicate = True
            else:
                seen_company_titles.add(combo)
                
        if not is_duplicate:
            if normalized_url:
                seen_urls.add(normalized_url)
            unique_jobs.append(job)
            
    return unique_jobs
