import asyncio
import os
import sys
from typing import List, Dict
import logging

# Add scraper dir to sys.path so its internal imports work
sys.path.append(os.path.dirname(__file__))

from companies import COMPANY_CONFIGS
from strategy import scrape_company_in_tab
from utils import flatten_jobs, deduplicate_jobs
from logger import setup_logger

log = setup_logger()

async def run_playwright_scraper(role: str, location: str) -> List[Dict]:
    configs = COMPANY_CONFIGS
    
    # Update search queries based on user's role
    for cfg in configs:
        if cfg.search:
            cfg.search.query = role

    all_results: dict[str, list[dict]] = {}

    user_data_dir = os.path.join(os.path.dirname(__file__), "user_data")
    
    async with async_playwright() as p:
        try:
            context = await p.chromium.launch_persistent_context(
                user_data_dir=user_data_dir,
                headless=True,  # Run headlessly in the background
            )
            
            tasks = [
                scrape_company_in_tab(context, cfg)
                for cfg in configs
            ]
            
            results_list = await asyncio.gather(*tasks)
            all_results = dict(results_list)
            
        except Exception as e:
            log.error(f"Playwright scraper failed: {e}")
            return []
        finally:
            try:
                await context.close()
            except:
                pass

    jobs = flatten_jobs(all_results)
    jobs = deduplicate_jobs(jobs)
    
    # Normalize keys for our existing compute_relevance logic
    normalized = []
    for j in jobs:
        normalized.append({
            "title": j.get("title", ""),
            "company": j.get("company", ""),
            "location": j.get("location", ""),
            "url": j.get("apply_url", ""),
            "description": j.get("department", ""), # use department as short description
            "portal": "playwright",
            "skills": "", # We don't extract skills directly in DOM, rely on title/dept
        })
        
    return normalized

def scrape_all(role: str, location: str) -> List[Dict]:
    """Synchronous wrapper for the orchestrator."""
    return asyncio.run(run_playwright_scraper(role, location))
