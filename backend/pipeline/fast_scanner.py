"""
Zero-token fast scanner — queries Greenhouse, Ashby, and Lever APIs
directly, applies title keyword filtering, smart ranking by role/location
relevance, and returns diverse results across companies.

Also queries DuckDuckGo for supplementary job results from LinkedIn,
Indeed, Glassdoor, etc.

No LLM tokens used — pure HTTP + JSON parsing.
"""
import logging
import requests
import re
import yaml
import os
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional
from backend.storage.cache import get_cached, set_cached

log = logging.getLogger(__name__)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "../../config/portals.yml")
FETCH_TIMEOUT = 10
MAX_WORKERS = 10


# ── Config ───────────────────────────────────────────────────────────

def load_portal_config() -> dict:
    try:
        with open(CONFIG_PATH, "r") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        log.warning(f"portals.yml not found at {CONFIG_PATH}")
        return {}


# ── API Detection (ported from scan.mjs) ─────────────────────────────

def detect_api(company: dict) -> Optional[dict]:
    """Auto-detect if a company uses Greenhouse, Ashby, or Lever from its config."""
    # Explicit Greenhouse API
    api = company.get("api", "")
    if api and "greenhouse" in api:
        return {"type": "greenhouse", "url": api}

    url = company.get("careers_url", "")

    # Ashby
    ashby_match = re.search(r"jobs\.ashbyhq\.com/([^/?#]+)", url)
    if ashby_match:
        slug = ashby_match.group(1)
        return {
            "type": "ashby",
            "url": f"https://api.ashbyhq.com/posting-api/job-board/{slug}?includeCompensation=true",
        }

    # Lever
    lever_match = re.search(r"jobs\.lever\.co/([^/?#]+)", url)
    if lever_match:
        slug = lever_match.group(1)
        return {
            "type": "lever",
            "url": f"https://api.lever.co/v0/postings/{slug}",
        }

    # Greenhouse EU boards
    gh_board_match = re.search(r"job-boards(?:\.eu)?\.greenhouse\.io/([^/?#]+)", url)
    if gh_board_match and not api:
        slug = gh_board_match.group(1)
        return {
            "type": "greenhouse",
            "url": f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
        }

    return None


# ── API Parsers (ported from scan.mjs) ───────────────────────────────

def parse_greenhouse(data: dict, company_name: str) -> List[Dict]:
    jobs = data.get("jobs", [])
    return [
        {
            "title":    j.get("title", ""),
            "url":      j.get("absolute_url", ""),
            "company":  company_name,
            "location": (j.get("location") or {}).get("name", ""),
            "portal":   "greenhouse",
            "updated_at": j.get("updated_at", ""),
            "description": _clean_html(j.get("content", "")),
        }
        for j in jobs
    ]


def parse_ashby(data: dict, company_name: str) -> List[Dict]:
    jobs = data.get("jobs", [])
    return [
        {
            "title":    j.get("title", ""),
            "url":      j.get("jobUrl", ""),
            "company":  company_name,
            "location": j.get("location", ""),
            "portal":   "ashby",
            "updated_at": j.get("updatedAt", ""),
            "description": j.get("descriptionPlain", "") or "",
        }
        for j in jobs
    ]


def parse_lever(data, company_name: str) -> List[Dict]:
    if not isinstance(data, list):
        return []
    return [
        {
            "title":    j.get("text", ""),
            "url":      j.get("hostedUrl", ""),
            "company":  company_name,
            "location": (j.get("categories") or {}).get("location", ""),
            "portal":   "lever",
            "updated_at": str(j.get("createdAt", "")),
            "description": j.get("descriptionPlain", "") or "",
        }
        for j in data
    ]


PARSERS = {
    "greenhouse": parse_greenhouse,
    "ashby":      parse_ashby,
    "lever":      parse_lever,
}


# ── Clean HTML helper ────────────────────────────────────────────────

def _clean_html(html_text: str) -> str:
    """Strip HTML tags and return plain text (first 500 chars)."""
    if not html_text:
        return ""
    clean = re.sub(r"<[^>]+>", " ", html_text)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:500]


# ── Title Filter ─────────────────────────────────────────────────────

def build_title_filter(config: dict, role_query: str = ""):
    """Returns a function that checks if a job title passes keyword filters.
    
    In addition to the static positive/negative lists from config,
    we also build dynamic positive keywords from the user's role query.
    """
    title_filter = config.get("title_filter", {})
    positive = [kw.lower() for kw in title_filter.get("positive", [])]
    negative = [kw.lower() for kw in title_filter.get("negative", [])]

    # Add user's role query words as dynamic positive keywords
    dynamic_positive = []
    if role_query:
        dynamic_positive = [w.lower() for w in role_query.strip().split() if len(w) > 2]

    def passes(title: str) -> bool:
        lower = title.lower()
        # Must match either static positive OR dynamic role keywords
        has_static = (not positive) or any(kw in lower for kw in positive)
        has_dynamic = any(kw in lower for kw in dynamic_positive) if dynamic_positive else False
        has_positive = has_static or has_dynamic
        has_negative = any(kw in lower for kw in negative)
        return has_positive and not has_negative

    return passes


# ── Role Relevance Scoring (IMPROVED) ────────────────────────────────

# Common role synonyms for better matching
ROLE_SYNONYMS = {
    "ml": ["machine learning", "ml", "deep learning", "dl"],
    "machine learning": ["ml", "machine learning", "deep learning", "dl"],
    "data scientist": ["data science", "data scientist", "ml", "machine learning", "analytics"],
    "data science": ["data scientist", "data science", "ml", "machine learning"],
    "data engineer": ["data engineering", "data engineer", "etl", "data pipeline"],
    "backend": ["backend", "back-end", "back end", "server-side", "api"],
    "frontend": ["frontend", "front-end", "front end", "ui", "react", "vue", "angular"],
    "full stack": ["fullstack", "full stack", "full-stack"],
    "fullstack": ["fullstack", "full stack", "full-stack"],
    "devops": ["devops", "sre", "platform engineer", "infrastructure"],
    "sre": ["sre", "site reliability", "devops", "platform"],
    "nlp": ["nlp", "natural language", "language model", "llm", "computational linguistics"],
    "llm": ["llm", "large language model", "nlp", "generative ai", "gen ai"],
    "ai": ["ai", "artificial intelligence", "ml", "machine learning", "deep learning"],
    "software engineer": ["software engineer", "software developer", "sde", "swe"],
    "software developer": ["software developer", "software engineer", "sde", "swe"],
    "research": ["research", "researcher", "research scientist", "research engineer"],
    "python": ["python", "backend", "django", "flask", "fastapi"],
}

# Experience level keywords for title matching
EXPERIENCE_FILTERS = {
    "intern":  {"positive": ["intern", "internship", "student", "co-op", "trainee"],
                "negative": ["senior", "staff", "principal", "lead", "manager", "director", "head", "vp"]},
    "entry":   {"positive": ["junior", "entry", "associate", "jr", "new grad", "graduate", "i", "1"],
                "negative": ["senior", "staff", "principal", "lead", "manager", "director", "head", "vp"]},
    "mid":     {"positive": ["mid", "ii", "2", "3"],
                "negative": ["intern", "junior", "senior", "staff", "principal", "lead", "manager", "director"]},
    "senior":  {"positive": ["senior", "sr", "iii", "iv", "3", "4"],
                "negative": ["intern", "junior", "staff", "principal", "vp", "director"]},
    "lead":    {"positive": ["lead", "staff", "principal", "head", "architect", "distinguished", "fellow"],
                "negative": ["intern", "junior"]},
}


def compute_relevance(job: dict, role_query: str, location_query: str, experience: str = "") -> float:
    """
    Score a job's relevance to the user's search query (0.0 to 1.0).
    Higher = more relevant. No LLM needed.
    
    Improved scoring with:
    - Synonym matching for roles
    - N-gram phrase matching (not just single words)
    - Experience level filtering
    - Description content matching
    """
    score = 0.0
    title_lower = job.get("title", "").lower()
    location_lower = job.get("location", "").lower()
    desc_lower = job.get("description", "").lower()[:500]
    role_lower = role_query.lower().strip()
    loc_lower = location_query.lower().strip()

    # ── ROLE MATCHING (0.0 - 0.55) ──

    # Exact phrase match in title → highest score
    if role_lower in title_lower:
        score += 0.55
    else:
        # Try synonym matching: expand user query with synonyms
        all_match_terms = set()
        all_match_terms.add(role_lower)
        for key, synonyms in ROLE_SYNONYMS.items():
            if key in role_lower or role_lower in key:
                all_match_terms.update(synonyms)
        
        # Also add individual words from the role query
        role_words = [w for w in role_lower.split() if len(w) > 1]
        all_match_terms.update(role_words)

        # Check how many match terms appear in the title
        matched_count = sum(1 for term in all_match_terms if term in title_lower)
        total_terms = len(all_match_terms) if all_match_terms else 1
        
        if matched_count > 0:
            # At least one synonym/word matched
            match_ratio = matched_count / total_terms
            score += 0.20 + (0.30 * min(match_ratio * 2, 1.0))
        else:
            # Check description as fallback
            desc_matched = sum(1 for term in all_match_terms if term in desc_lower)
            if desc_matched > 0:
                score += 0.10 * min(desc_matched / total_terms * 2, 1.0)

    # ── LOCATION MATCHING (0.0 - 0.25) ──

    if loc_lower:
        loc_words = loc_lower.split()
        if loc_lower in location_lower:
            score += 0.25
        elif "remote" in location_lower:
            score += 0.20  # Remote jobs are good matches for any location
        else:
            # Partial location matching
            matched = sum(1 for w in loc_words if w in location_lower)
            if loc_words and matched > 0:
                score += 0.15 * (matched / len(loc_words))

    # ── EXPERIENCE LEVEL MATCHING (0.0 - 0.15) ──

    if experience and experience in EXPERIENCE_FILTERS:
        exp_config = EXPERIENCE_FILTERS[experience]
        exp_positive = exp_config["positive"]
        exp_negative = exp_config["negative"]

        title_words = title_lower.split()
        
        # Check for positive experience signals
        has_exp_match = any(kw in title_lower for kw in exp_positive)
        # Check for negative experience signals
        has_exp_mismatch = any(kw in title_lower for kw in exp_negative)

        if has_exp_match and not has_exp_mismatch:
            score += 0.15  # Perfect experience match
        elif not has_exp_match and not has_exp_mismatch:
            score += 0.08  # Neutral (no level mentioned)
        elif has_exp_mismatch:
            score -= 0.10  # Penalize wrong level
    else:
        score += 0.05  # No experience filter — small neutral bonus

    # ── BONUS: Title conciseness (0.0 - 0.05) ──
    # Very long titles are often too niche or compound roles
    title_word_count = len(title_lower.split())
    if title_word_count <= 5:
        score += 0.05
    elif title_word_count <= 8:
        score += 0.02

    return max(0.0, min(score, 1.0))


# ── Fetch Single Company ────────────────────────────────────────────

def fetch_company(company: dict) -> List[Dict]:
    """Fetch all jobs from a single company's API. Returns parsed list."""
    api_info = detect_api(company)
    if not api_info:
        return []

    company_name = company.get("name", "Unknown")
    api_type = api_info["type"]
    api_url = api_info["url"]

    try:
        resp = requests.get(api_url, timeout=FETCH_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
        jobs = PARSERS[api_type](data, company_name)
        log.info(f"{api_type.capitalize()} API: {len(jobs)} jobs from {company_name}")
        return jobs
    except Exception as e:
        log.warning(f"{api_type.capitalize()} API failed for {company_name}: {e}")
        return []


# ── DuckDuckGo Web Search ───────────────────────────────────────────

def search_duckduckgo(role: str, location: str, max_results: int = 20) -> List[Dict]:
    """Search DuckDuckGo for job postings from major job boards."""
    try:
        from duckduckgo_search import DDGS
        queries = [
            f"{role} {location} jobs hiring now",
            f'"{role}" jobs {location} site:linkedin.com OR site:lever.co OR site:greenhouse.io',
        ]
        all_results = []
        seen = set()
        
        with DDGS() as ddgs:
            for query in queries:
                try:
                    results = list(ddgs.text(query, max_results=max_results // 2, timelimit="m"))
                    for r in results:
                        url = r.get("href") or r.get("url", "")
                        title = r.get("title", "Job Posting")
                        snippet = r.get("body", "")
                        
                        # Skip non-job URLs
                        if not url or any(skip in url for skip in [
                            "youtube.com", "wikipedia.org", "reddit.com",
                            "facebook.com", "twitter.com", "quora.com"
                        ]):
                            continue
                        
                        # Dedup by URL
                        url_clean = url.split("?")[0].rstrip("/")
                        if url_clean in seen:
                            continue
                        seen.add(url_clean)
                        
                        all_results.append({
                            "title": _clean_ddg_title(title),
                            "url": url_clean,
                            "company": _extract_company_from_title(title),
                            "location": location,
                            "portal": "web",
                            "updated_at": "",
                            "description": snippet[:500],
                        })
                except Exception as e:
                    log.warning(f"DDG query failed for '{query[:50]}...': {e}")
                    continue
        
        log.info(f"DuckDuckGo search: {len(all_results)} results")
        return all_results
        
    except ImportError:
        log.warning("duckduckgo-search package not installed, trying ddgs...")
        return _search_ddgs_fallback(role, location, max_results)
    except Exception as e:
        log.warning(f"DuckDuckGo search failed: {e}")
        return _search_ddgs_fallback(role, location, max_results)


def _search_ddgs_fallback(role: str, location: str, max_results: int = 20) -> List[Dict]:
    """Fallback using the ddgs package."""
    try:
        from ddgs import DDGS
        query = f"{role} {location} jobs site:linkedin.com OR site:indeed.com OR site:glassdoor.com"
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results, timelimit="m"))
            output = []
            for r in results:
                url = r.get("href") or r.get("url", "")
                title = r.get("title", "Job Posting")
                if url:
                    output.append({
                        "title": _clean_ddg_title(title),
                        "url": url.split("?")[0].rstrip("/"),
                        "company": _extract_company_from_title(title),
                        "location": location,
                        "portal": "web",
                        "updated_at": "",
                        "description": r.get("body", "")[:500],
                    })
            log.info(f"DDG fallback: {len(output)} results")
            return output
    except Exception as e:
        log.warning(f"DDG fallback also failed: {e}")
        return []


def _clean_ddg_title(title: str) -> str:
    """Clean up search result titles — remove site names and cruft."""
    # Remove common suffixes like "| LinkedIn", "- Indeed", etc.
    for suffix in [" | LinkedIn", " - LinkedIn", " | Indeed", " - Indeed",
                   " | Glassdoor", " - Glassdoor", " | Lever", " - Lever",
                   " | Greenhouse", " - Greenhouse"]:
        if title.endswith(suffix):
            title = title[:-len(suffix)]
    return title.strip()


def _extract_company_from_title(title: str) -> str:
    """Try to extract company name from search result title."""
    separators = [" - ", " | ", " at ", " @ "]
    for sep in separators:
        if sep in title:
            parts = title.split(sep)
            if len(parts) >= 2:
                return parts[-1].strip()
    return "Unknown"


# ── Main Entry Point ────────────────────────────────────────────────

def fast_scan(role: str, location: str, experience: str = "", max_results: int = 40) -> List[Dict]:
    """
    Main entry point for the zero-token fast scanner.
    
    1. Reads portals.yml for tracked companies
    2. Fetches all ATS APIs concurrently (Greenhouse, Ashby, Lever)
    3. Searches DuckDuckGo for supplementary results (always-on)
    4. Applies title keyword filter  
    5. Scores relevance to user's role/location/experience query
    6. Deduplicates and ensures company diversity
    7. Returns top N results sorted by relevance
    """
    # Check cache first
    cache_key = hashlib.md5(f"fast|{role}|{location}|{experience}".encode()).hexdigest()
    cached = get_cached(cache_key)
    if cached:
        log.info("Fast scan cache hit — returning cached results")
        return cached[:max_results]

    config = load_portal_config()
    companies = [c for c in config.get("tracked_companies", []) if c.get("enabled", True)]
    title_filter = build_title_filter(config, role_query=role)

    if not companies:
        log.warning("No enabled companies in portals.yml")

    # Concurrent API fetch — ATS + DuckDuckGo in parallel
    all_jobs = []
    with ThreadPoolExecutor(max_workers=MAX_WORKERS + 2) as executor:
        # Submit ATS company fetches
        futures = {}
        for c in companies:
            futures[executor.submit(fetch_company, c)] = c.get("name", "ATS")
        
        # Submit DuckDuckGo search in parallel
        ddg_future = executor.submit(search_duckduckgo, role, location, 20)
        futures[ddg_future] = "DuckDuckGo"

        for future in as_completed(futures):
            source = futures[future]
            try:
                jobs = future.result()
                all_jobs.extend(jobs)
            except Exception as e:
                log.warning(f"Failed to fetch from {source}: {e}")

    log.info(f"Total raw jobs fetched: {len(all_jobs)}")

    # Apply title keyword filter
    filtered = [j for j in all_jobs if title_filter(j.get("title", ""))]
    log.info(f"After title filter: {len(filtered)} jobs")

    # Score relevance
    for job in filtered:
        job["relevance"] = compute_relevance(job, role, location, experience)

    # Deduplicate by URL
    seen_urls = set()
    unique = []
    for job in filtered:
        url = job.get("url", "").split("?")[0].rstrip("/")
        if url and url not in seen_urls:
            seen_urls.add(url)
            job["url"] = url
            unique.append(job)

    log.info(f"After dedup: {len(unique)} unique jobs")

    # Filter out very low relevance (< 0.1) — these are likely irrelevant noise
    MIN_RELEVANCE = 0.10
    relevant = [j for j in unique if j.get("relevance", 0) >= MIN_RELEVANCE]
    log.info(f"After relevance filter (>= {MIN_RELEVANCE}): {len(relevant)} jobs")

    # Sort by relevance (highest first)
    relevant.sort(key=lambda j: j.get("relevance", 0), reverse=True)

    # Ensure company diversity: round-robin so no single company dominates
    diverse = _diversify(relevant, max_results)

    # Cache the results
    if diverse:
        set_cached(cache_key, diverse)

    log.info(f"Fast scan complete: returning {len(diverse)} jobs")
    return diverse


def _diversify(jobs: List[Dict], max_count: int) -> List[Dict]:
    """
    Round-robin selection across companies to ensure diversity.
    Within each company's pool, jobs are already sorted by relevance.
    """
    if len(jobs) <= max_count:
        return jobs

    # Group by company
    company_pools = {}
    for job in jobs:
        company = job.get("company", "Unknown")
        if company not in company_pools:
            company_pools[company] = []
        company_pools[company].append(job)

    # Round-robin pick
    result = []
    company_names = list(company_pools.keys())
    idx = 0
    while len(result) < max_count:
        picked_any = False
        for name in company_names:
            pool = company_pools[name]
            if idx < len(pool):
                result.append(pool[idx])
                picked_any = True
                if len(result) >= max_count:
                    break
        if not picked_any:
            break
        idx += 1

    return result
