"""
Two-tier content fetcher:
1. Trafilatura (fast, no JS) — works for ~60% of pages
2. Playwright headless (slower, full JS) — for React SPA job boards
"""
import logging
import trafilatura
from backend.config import MIN_CONTENT_LENGTH, PLAYWRIGHT_TIMEOUT

log = logging.getLogger(__name__)

def fetch_with_trafilatura(url: str) -> str:
    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return ""
        text = trafilatura.extract(downloaded, include_comments=False,
                                   include_tables=True, no_fallback=False)
        return text or ""
    except Exception as e:
        log.warning(f"Trafilatura failed on {url}: {e}")
        return ""

def fetch_with_playwright(url: str) -> str:
    """
    Launches headless Chromium, waits for network idle,
    returns visible text. Slower (~5s) but handles SPAs.
    Install: pip install playwright && playwright install chromium
    """
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                           "AppleWebKit/537.36 (KHTML, like Gecko) "
                           "Chrome/121.0.0.0 Safari/537.36"
            )
            page.goto(url, wait_until="networkidle", timeout=PLAYWRIGHT_TIMEOUT)
            # Wait for common job content selectors
            for selector in ["[class*='job-description']", "[class*='description']",
                             "[class*='content']", "main", "article"]:
                try:
                    page.wait_for_selector(selector, timeout=3000)
                    break
                except:
                    continue
            text = page.inner_text("body")
            browser.close()
            return text[:8000]   # cap at 8K chars — LLM context limit
    except Exception as e:
        log.warning(f"Playwright failed on {url}: {e}")
        return ""

def fetch_job_content(url: str) -> str:
    """
    Main fetcher. Returns clean text or empty string.
    Automatically escalates to Playwright if Trafilatura content is thin.
    """
    text = fetch_with_trafilatura(url)
    if len(text) >= MIN_CONTENT_LENGTH:
        log.debug(f"Trafilatura OK ({len(text)} chars): {url}")
        return text

    log.info(f"Trafilatura thin ({len(text)} chars), escalating to Playwright: {url}")
    pw_text = fetch_with_playwright(url)
    return pw_text if len(pw_text) > len(text) else text