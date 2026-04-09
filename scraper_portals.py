
import asyncio
import yaml
from datetime import datetime
from typing import List, Dict
from playwright.async_api import async_playwright
import re

class PortalScraper:
    """Multi-portal job scraper using Playwright for real-time scraping"""
    
    def __init__(self, config_path: str = "config/portals.yml"):
        self.config = self._load_config(config_path)
        self.jobs = []
        self.positive_keywords = self.config.get('title_filter', {}).get('positive', [])
        self.negative_keywords = self.config.get('title_filter', {}).get('negative', [])
    
    def _load_config(self, path: str) -> dict:
        """Load portal configuration from YAML"""
        try:
            with open(path, 'r') as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            print(f"⚠️ Config file not found: {path}")
            return {}
    
    def _is_title_valid(self, title: str) -> bool:
        """Check if job title matches positive keywords and avoids negative ones"""
        title_lower = title.lower()
        
        # Must have at least one positive keyword
        has_positive = any(kw.lower() in title_lower for kw in self.positive_keywords)
        # Must not have negative keywords
        has_negative = any(kw.lower() in title_lower for kw in self.negative_keywords)
        
        return has_positive and not has_negative
    
    async def scrape_ashby(self) -> List[Dict]:
        """Scrape Ashby portal for jobs"""
        print("[🌐 Scraping Ashby portal...]")
        jobs = []
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto("https://jobs.ashbyhq.com/", timeout=30000)
                await page.wait_for_timeout(3000)
                
                # Extract job listings
                job_elements = await page.query_selector_all('[data-testid="job-board-job-card"]')
                
                for job_elem in job_elements[:10]:  # Limit to 10 jobs
                    try:
                        title = await job_elem.query_selector('.job-title')
                        company = await job_elem.query_selector('.company-name')
                        location = await job_elem.query_selector('.job-location')
                        
                        title_text = await title.inner_text() if title else "Unknown"
                        
                        if self._is_title_valid(title_text):
                            jobs.append({
                                'portal': 'Ashby',
                                'title': title_text,
                                'company': await company.inner_text() if company else "Unknown",
                                'location': await location.inner_text() if location else "Unknown",
                                'url': await job_elem.get_attribute('href') or "N/A",
                                'scraped_at': datetime.now().isoformat()
                            })
                    except Exception as e:
                        print(f"  ⚠️ Error parsing job element: {e}")
                        continue
                
                await browser.close()
        except Exception as e:
            print(f"❌ Ashby scrape failed: {e}")
        
        print(f"✅ Found {len(jobs)} jobs on Ashby")
        return jobs
    
    async def scrape_greenhouse(self) -> List[Dict]:
        """Scrape Greenhouse portal for jobs"""
        print("[🌐 Scraping Greenhouse portal...]")
        jobs = []
        
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                await page.goto("https://boards.greenhouse.io/", timeout=30000)
                await page.wait_for_timeout(3000)
                
                # Extract job listings
                job_elements = await page.query_selector_all('[data-track-event-name="job_click"]')
                
                for job_elem in job_elements[:10]:
                    try:
                        title = await job_elem.query_selector('.opening__title')
                        department = await job_elem.query_selector('.opening__department')
                        location = await job_elem.query_selector('.opening__location')
                        
                        title_text = await title.inner_text() if title else "Unknown"
                        
                        if self._is_title_valid(title_text):
                            jobs.append({
                                'portal': 'Greenhouse',
                                'title': title_text,
                                'company': await department.inner_text() if department else "Unknown",
                                'location': await location.inner_text() if location else "Unknown",
                                'url': await job_elem.get_attribute('href') or "N/A",
                                'scraped_at': datetime.now().isoformat()
                            })
                    except Exception as e:
                        print(f"  ⚠️ Error parsing job element: {e}")
                        continue
                
                await browser.close()
        except Exception as e:
            print(f"❌ Greenhouse scrape failed: {e}")
        
        print(f"✅ Found {len(jobs)} jobs on Greenhouse")
        return jobs
    
    async def scrape_all(self) -> List[Dict]:
        """Run all scrapers in parallel"""
        print("\n[🚀 Starting multi-portal job scraping...]")
        
        results = await asyncio.gather(
            self.scrape_ashby(),
            self.scrape_greenhouse(),
            return_exceptions=True
        )
        
        self.jobs = []
        for result in results:
            if isinstance(result, list):
                self.jobs.extend(result)
            elif isinstance(result, Exception):
                print(f"❌ Scraper error: {result}")
        
        print(f"\n[✅ Total jobs found: {len(self.jobs)}]")
        return self.jobs
    
    def save_jobs(self, filename: str = "data/scraped_jobs.json"):
        """Save scraped jobs to JSON file"""
        import json
        try:
            with open(filename, 'w') as f:
                json.dump(self.jobs, f, indent=2)
            print(f"✅ Jobs saved to {filename}")
        except Exception as e:
            print(f"❌ Failed to save jobs: {e}")


# Standalone usage
if __name__ == "__main__":
    scraper = PortalScraper()
    jobs = asyncio.run(scraper.scrape_all())
    scraper.save_jobs()
    
    print("\n📊 Sample jobs:")
    for job in jobs[:3]:
        print(f"  • {job['title']} @ {job['company']} ({job['portal']})")
