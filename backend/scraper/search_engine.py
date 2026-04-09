"""
Search engine with fallback chain:
DuckDuckGo → Bing Web Search API (free) → Google CSE (free)
Never raises — returns empty list on total failure.
"""
import hashlib, time, logging
from duckduckgo_search import DDGS
from backend.config import PORTALS, MAX_JOBS_PER_RUN
from backend.storage.cache import get_cached, set_cached

log = logging.getLogger(__name__)

import urllib.request, urllib.parse, ssl, re

def build_query(role: str, location: str, portal_filter: str) -> str:
    loc = location if location else ""
    return f"{role} {loc} {portal_filter}"

def search_duckduckgo(query: str, max_results: int) -> list[dict]:
    """Highly robust fallback using DuckDuckGo Lite HTML without third-party library constraints."""
    try:
        url = "https://lite.duckduckgo.com/lite/"
        data = urllib.parse.urlencode({'q': query}).encode('utf-8')
        req = urllib.request.Request(
            url, 
            data=data, 
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        context = ssl._create_unverified_context()
        
        with urllib.request.urlopen(req, context=context, timeout=10) as response:
            html = response.read().decode('utf-8')
        
        results = []
        links = re.findall(r'<a rel="nofollow" href="(http[^"]+)"', html)
        
        for link in links:
            if "duckduckgo.com" in link or "youtube.com" in link: continue
            results.append({"title": "Job Posting", "url": link, "snippet": ""})
            if len(results) >= max_results: break
            
        if not results:
            log.warning(f"DuckDuckGo Lite returned zero matches for: {query}")
        return results
    except Exception as e:
        log.warning(f"DuckDuckGo Lite fetch failed for '{query[:50]}': {e}")
        return []

def search_bing_free(query: str, max_results: int) -> list[dict]:
    """
    Uses Bing Web Search API — 1000 free calls/month.
    Set BING_API_KEY in .env (get free key at portal.azure.com).
    """
    import os, requests
    key = os.getenv("BING_API_KEY", "")
    if not key:
        return []
    try:
        resp = requests.get(
            "https://api.bing.microsoft.com/v7.0/search",
            headers={"Ocp-Apim-Subscription-Key": key},
            params={"q": query, "count": max_results, "mkt": "en-IN"},
            timeout=10
        )
        data = resp.json()
        return [{"title": v.get("name",""), "url": v.get("url",""), "snippet": v.get("snippet","")}
                for v in data.get("webPages",{}).get("value",[])]
    except Exception as e:
        log.warning(f"Bing failed: {e}")
        return []

def search_all_portals(role: str, location: str) -> list[dict]:
    """
    Main entry point. Searches all portals with DDG + Bing fallback.
    Returns deduplicated list of raw job hits (not yet extracted).
    Caches by query hash for CACHE_TTL_HOURS.
    """
    cache_key = hashlib.md5(f"{role}|{location}".encode()).hexdigest()
    cached = get_cached(cache_key)
    if cached:
        log.info("Cache hit — returning cached results")
        return cached

    all_results = []
    seen_urls = set()

    for portal, (site_filter, max_r) in PORTALS.items():
        query = build_query(role, location, site_filter)
        results = search_duckduckgo(query, max_r)
        if not results:
            log.info(f"DDG returned 0 for {portal}, trying Bing fallback")
            results = search_bing_free(query, max_r)

        for r in results:
            url = r["url"]
            # Normalize URL — strip tracking params
            base_url = url.split("?")[0].rstrip("/")
            if base_url not in seen_urls:
                seen_urls.add(base_url)
                r["portal"] = portal
                r["url"] = base_url
                all_results.append(r)

        time.sleep(1.5)   # polite delay between portal searches

    if all_results:
        log.info(f"Total unique URLs found: {len(all_results)}")
        set_cached(cache_key, all_results)
    else:
        log.warning("No URLs found across all portals; not caching this empty result.")
        
    return all_results[:MAX_JOBS_PER_RUN]