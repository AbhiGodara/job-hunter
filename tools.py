import re
from crewai.tools import tool

try:
    from ddgs import DDGS
    import trafilatura
except ImportError:
    try:
        from duckduckgo_search import DDGS
        import trafilatura
    except ImportError:
        pass


def search_jobs(query: str) -> list[dict]:
    """
    Standalone function (NOT a CrewAI tool) that searches and scrapes job listings.
    Called directly from Python before the crew starts, so the LLM never gets the chance to skip it.
    """
    print(f"\n[🔍 Searching the web for]: {query}")

    # Target ATS platforms for direct, real application links
    optimized_query = f"{query} (site:greenhouse.io OR site:lever.co OR site:workable.com OR site:jobs.ashbyhq.com OR site:applytojob.com)"

    cleaned_chunks = []

    with DDGS() as ddgs:
        try:
            results = list(ddgs.text(optimized_query, timelimit="m", max_results=5))
            if len(results) < 2:
                print("[⚠️ ATS search too narrow, broadening search...]")
                results = list(ddgs.text(query, timelimit="m", max_results=5))
        except Exception as e:
            print(f"[❌ Search Error]: {e}")
            return []

    print(f"[✅ Found {len(results)} links, scraping content...]")

    for i, result in enumerate(results):
        url = result.get("href", "")
        title = result.get("title", "")
        snippet = result.get("body", "")

        markdown = snippet  # Fallback

        try:
            downloaded = trafilatura.fetch_url(url)
            if downloaded:
                extracted = trafilatura.extract(downloaded)
                if extracted:
                    markdown = extracted
        except Exception:
            pass  # Use snippet fallback

        if markdown:
            cleaned = re.sub(r"\[[^\]]+\]\([^\)]+\)|https?://[^\s]+", "", markdown)
            cleaned_chunks.append(
                {
                    "title": title,
                    "url": url,
                    "content": cleaned[:1500],
                }
            )
            print(f"  [{i+1}] ✅ {title[:80]}")

    print(f"\n[🎯 Successfully scraped {len(cleaned_chunks)} job pages!]\n")
    return cleaned_chunks


@tool
def company_web_search_tool(query: str):
    """
    Web Search Tool for company research only.
    Args:
        query: str
            The query to search the web for.
    Returns
        A list of search results with the website content in Markdown format.
    """
    print(f"\n[🔍 Company Research]: {query}")

    cleaned_chunks = []

    with DDGS() as ddgs:
        try:
            results = list(ddgs.text(query, max_results=5))
        except Exception as e:
            return f"Error: {e}"

    for result in results:
        url = result.get("href", "")
        title = result.get("title", "")
        snippet = result.get("body", "")

        markdown = snippet
        try:
            downloaded = trafilatura.fetch_url(url)
            if downloaded:
                extracted = trafilatura.extract(downloaded)
                if extracted:
                    markdown = extracted
        except Exception:
            pass

        if markdown:
            cleaned = re.sub(r"\[[^\]]+\]\([^\)]+\)|https?://[^\s]+", "", markdown)
            cleaned_chunks.append(
                {"title": title, "url": url, "markdown": cleaned[:3000]}
            )

    return cleaned_chunks
