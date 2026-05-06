import asyncio
import random
import re
import sqlite3
import urllib.parse
from typing import Optional
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

# Local imports
from .config_loader import AppConfig
from .database import JobRepository, DatabaseManager
from .parser import SeekParser
from .pipeline import AgentPipeline

class SeekCollector:
    def __init__(self, db_manager: JobRepository, config: AppConfig, pipeline: Optional[AgentPipeline] = None):
        self.db = db_manager
        self.config = config
        self.pipeline = pipeline
        self.parser = SeekParser()
        self.base_url = "https://nz.seek.com"
        self.stealth = Stealth()

    async def _get_browser_context(self, playwright):
        browser = await playwright.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
        )
        return browser, context

    async def scrape(self, limit=None):
        async with async_playwright() as p:
            browser, context = await self._get_browser_context(p)
            page = await context.new_page()
            await self.stealth.apply_stealth_async(page)

            try:
                searches = self.config.searches
                locations = self.config.locations
                
                jobs_count = 0
                for search in searches:
                    if limit and jobs_count >= limit:
                        break

                    keywords = search.keywords
                    priority = search.priority
                    
                    relevant_locations = [loc for loc in locations if loc.priority == priority]
                    
                    for loc in relevant_locations:
                        if limit and jobs_count >= limit:
                            break

                        loc_slug = loc.slug
                        print(f"Searching for '{keywords}' in '{loc.name}' ({loc_slug})...")
                        
                        # Human-readable URL format: /<role>-jobs/in-<location>
                        keyword_slug = re.sub(r'[^a-z0-9]+', '-', keywords.lower()).strip('-')
                        search_url = f"{self.base_url}/{keyword_slug}-jobs/in-{loc_slug}"
                        
                        new_jobs = await self.scrape_search_results(page, search_url, limit=(limit - jobs_count) if limit else None)
                        jobs_count += new_jobs
                        
                        if limit and jobs_count >= limit:
                            break

                        # Random jitter
                        await asyncio.sleep(random.uniform(2, 5))

            finally:
                await browser.close()

    async def scrape_search_results(self, page, url, limit=None):
        await page.goto(url, wait_until="networkidle")
        
        # GUARD 1: Check if we are actually on Seek (not blocked)
        if not await page.query_selector('[data-automation="seek"]'):
            print(f"FAILED: Page integrity check failed for {url}. Possible bot detection.")
            return 0

        # Wait for Seek to settle its Redux state
        try:
            await page.wait_for_function("""
                (window.SEEK_REDUX_DATA && window.SEEK_REDUX_DATA.results.isLoading === false) ||
                document.querySelector('script[data-automation="server-state"]')
            """, timeout=10000)
        except Exception:
            pass # We'll try extraction anyway

        # Extract Redux data for advanced filtering and discovery
        redux = await page.evaluate("window.SEEK_REDUX_DATA")
        html = await page.content()
        
        # Use Parser to extract all jobs on the page
        all_jobs = self.parser.parse_search_results(redux_data=redux or {}, html=html)
        
        if not all_jobs:
            print(f"Zero results for {url}")
            return 0

        # LOG SUGGESTIONS: Capture related searches for AI discovery
        if redux and 'results' in redux:
            related = redux.get('results', {}).get('relatedSearches', [])
            source_keyword = redux.get('results', {}).get('locationWhere', 'Unknown')
            for item in related:
                self.db.log_suggestion(item.get('keywords'), source_keyword, item.get('totalJobs'))

        # Filter new jobs
        jobs_to_scrape = []
        for job in all_jobs:
            if limit and len(jobs_to_scrape) >= limit:
                break

            # Post-scrape location filter (Defense-in-depth against AU leakage)
            if not self._is_valid_nz_location(job['location']):
                continue

            # Check if exists in DB by Seek ID
            if self.is_already_scraped(job['seek_job_id']):
                continue
                
            jobs_to_scrape.append(job)

        if not jobs_to_scrape:
            return 0

        print(f"Scraping details for {len(jobs_to_scrape)} new jobs concurrently...")
        
        semaphore = asyncio.Semaphore(3)
        
        async def sem_scrape(job):
            async with semaphore:
                print(f"Fetching details for: {job['title']}...")
                raw_text = await self.scrape_job_details(page.context, job['url'])
                if raw_text:
                    # Update job dict with details
                    job['raw_text'] = raw_text
                    self.db.upsert_job(job)
                    self.db.log_action("scrape", f"Saved job: {job['title']} at {job['company']} (ID: {job['seek_job_id']})")
                    
                    if self.pipeline:
                        self.pipeline.push(job['seek_job_id'])
                        
                    return True
                return False

        results = await asyncio.gather(*[sem_scrape(j) for j in jobs_to_scrape])
        return sum(1 for r in results if r)

    def _extract_job_id(self, url):
        """DEPRECATED: Moved to SeekParser."""
        return self.parser._extract_job_id(url)

    def _clean_url(self, url):
        """Strip tracking parameters from URL."""
        if '?' in url:
            return url.split('?')[0]
        return url

    def _is_valid_nz_location(self, location_text):
        """Defense-in-depth: Ensure the location is not in Australia."""
        if not location_text:
            return True
        au_indicators = [
            "VIC", "NSW", "QLD", "WA", "SA", "TAS", "NT", "ACT",
            "Melbourne", "Sydney", "Brisbane", "Perth", "Adelaide", "Hobart", "Canberra", "Darwin",
            "Southbank", "Footscray", "Australia"
        ]
        
        for indicator in au_indicators:
            pattern = rf"\b{re.escape(indicator)}\b"
            if re.search(pattern, location_text, re.IGNORECASE):
                return False
        return True

    def is_already_scraped(self, seek_job_id):
        if not seek_job_id:
            return False
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM jobs WHERE seek_job_id = ?", (seek_job_id,))
            result = cursor.fetchone()
        return result is not None

    async def scrape_job_details(self, context, url):
        page = await context.new_page()
        await self.stealth.apply_stealth_async(page)
        try:
            await page.goto(url)
            # Wait for job description
            await page.wait_for_selector('[data-automation="jobAdDetails"]', timeout=10000)
            html = await page.content()
            return self.parser.parse_job_details(html)
        except Exception as e:
            print(f"Error scraping details for {url}: {e}")
        finally:
            await page.close()
        return None

    def save_job(self, title, company, location, url, raw_text, seek_job_id):
        """DEPRECATED: Use JobRepository.upsert_job instead."""
        self.db.upsert_job({
            "title": title,
            "company": company,
            "location": location,
            "url": url,
            "raw_text": raw_text,
            "seek_job_id": seek_job_id
        })

if __name__ == "__main__":
    import asyncio
    config = AppConfig.load()
    db_manager = DatabaseManager()
    collector = SeekCollector(db_manager, config)
    asyncio.run(collector.scrape())
