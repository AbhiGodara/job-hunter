"""
Enhanced multi-portal job scraper.
Searches across multiple job platforms via DuckDuckGo proxy,
deduplicates results, and extracts clean content.
"""

import re
import time
import hashlib
from typing import List, Dict, Optional
try:
    from ddgs import DDGS
except ImportError:
    from duckduckgo_search import DDGS
import trafilatura


# Portal search patterns
PORTAL_QUERIES = {
    "ats": {
        "label": "ATS Platforms (Greenhouse, Lever, Workable)",
        "query": '(site:greenhouse.io OR site:lever.co OR site:workable.com) "{position}" "{location}"',
        "max_results": 5,
    },
    "linkedin": {
        "label": "LinkedIn Jobs",
        "query": 'site:linkedin.com/jobs "{position}" "{location}"',
        "max_results": 5,
    },
    "indeed": {
        "label": "Indeed",
        "query": 'site:indeed.com "{position}" "{location}"',
        "max_results": 5,
    },
    "naukri": {
        "label": "Naukri (India)",
        "query": 'site:naukri.com "{position}" "{location}"',
        "max_results": 4,
    },
    "glassdoor": {
        "label": "Glassdoor",
        "query": 'site:glassdoor.com/job-listing "{position}" "{location}"',
        "max_results": 4,
    },
    "wellfound": {
        "label": "Wellfound (AngelList)",
        "query": 'site:wellfound.com "{position}" "{location}"',
        "max_results": 3,
    },
    "simplyhired": {
        "label": "SimplyHired",
        "query": 'site:simplyhired.com "{position}" "{location}"',
        "max_results": 3,
    },
}

# Date range mapping for DuckDuckGo timelimit parameter
DATE_RANGE_MAP = {
    "1_week": "w",
    "2_weeks": "w",
    "1_month": "m",
    "3_months": "m",
    "all": None,
}


def _normalize_url(url: str) -> str:
    """Normalize URL for deduplication."""
    url = url.lower().rstrip("/")
    # Remove tracking parameters
    url = re.sub(r"\?.*$", "", url)
    return url


def _url_hash(url: str) -> str:
    """Generate a hash for deduplication."""
    return hashlib.md5(_normalize_url(url).encode()).hexdigest()


def _scrape_content(url: str, max_chars: int = 1500) -> Optional[str]:
    """Scrape and clean content from a URL."""
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return None
        content = trafilatura.extract(downloaded)
        if not content or len(content.strip()) < 100:
            return None
        return content.strip()[:max_chars]
    except Exception:
        return None


def search_jobs(
    position: str,
    location: str,
    level: str = "",
    portals: List[str] = None,
    date_range: str = "1_month",
    max_total: int = 20,
    content_max_chars: int = 1500,
    on_progress=None,
) -> List[Dict]:
    """
    Search for jobs across multiple portals.

    Args:
        position: Job title/position to search for
        location: Job location
        level: Seniority level (Junior, Senior, etc.)
        portals: List of portal keys to search (defaults to all)
        date_range: One of '1_week', '2_weeks', '1_month', '3_months', 'all'
        max_total: Maximum total jobs to return
        content_max_chars: Max characters per job content
        on_progress: Callback function(message: str, progress: float)

    Returns:
        List of job dicts with title, url, content, source
    """
    if portals is None:
        portals = list(PORTAL_QUERIES.keys())

    timelimit = DATE_RANGE_MAP.get(date_range, "m")
    full_position = f"{level} {position}".strip() if level else position

    # Phase 1: Collect URLs from all portals
    seen_hashes = set()
    all_results = []

    def _progress(msg, pct):
        if on_progress:
            on_progress(msg, pct)
        print(f"[Scraper] {msg}")

    total_portals = len(portals)
    for idx, portal_key in enumerate(portals):
        portal = PORTAL_QUERIES.get(portal_key)
        if not portal:
            continue

        query = portal["query"].format(position=full_position, location=location)
        max_results = portal["max_results"]

        _progress(
            f"Searching {portal['label']}... ({idx+1}/{total_portals})",
            (idx / total_portals) * 0.4,
        )

        try:
            with DDGS() as ddgs:
                if timelimit:
                    results = list(ddgs.text(query, timelimit=timelimit, max_results=max_results))
                else:
                    results = list(ddgs.text(query, max_results=max_results))

                for r in results:
                    url = r.get("href", r.get("url", ""))
                    title = r.get("title", "")
                    h = _url_hash(url)

                    if h not in seen_hashes and url:
                        seen_hashes.add(h)
                        all_results.append({
                            "title": title,
                            "url": url,
                            "source": portal_key,
                            "source_label": portal["label"],
                        })
        except Exception as e:
            _progress(f"⚠️ Failed to search {portal['label']}: {str(e)[:80]}", 0)

        # Small delay between portal searches to avoid rate limiting
        time.sleep(0.5)

    _progress(f"Found {len(all_results)} unique job links across {total_portals} portals", 0.4)

    # Cap total results
    all_results = all_results[:max_total]

    # Phase 2: Scrape content from each URL
    scraped_jobs = []
    total_to_scrape = len(all_results)

    for i, item in enumerate(all_results):
        _progress(
            f"Scraping [{i+1}/{total_to_scrape}]: {item['title'][:60]}...",
            0.4 + (i / total_to_scrape) * 0.6,
        )

        content = _scrape_content(item["url"], max_chars=content_max_chars)
        if content:
            scraped_jobs.append({
                "title": item["title"],
                "url": item["url"],
                "content": content,
                "source": item["source"],
                "source_label": item["source_label"],
            })
        else:
            _progress(f"  ⚠️ Could not extract content from {item['url'][:60]}", 0)

        time.sleep(0.3)  # Polite delay

    _progress(f"✅ Successfully scraped {len(scraped_jobs)} job pages!", 1.0)
    return scraped_jobs
