import asyncio
import random
import re
import sqlite3
import urllib.parse
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

# Local imports
from .config_loader import load_config
from .database import DatabaseManager

class SeekCollector:
    def __init__(self, db_manager: DatabaseManager, config: dict):
        self.db = db_manager
        self.config = config
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
                searches = self.config.get('searches', [])
                locations = self.config.get('locations', [])
                
                jobs_count = 0
                for search in searches:
                    if limit and jobs_count >= limit:
                        break

                    keywords = search['keywords']
                    priority = search.get('priority', 1)
                    
                    relevant_locations = [loc for loc in locations if loc.get('priority') == priority]
                    
                    for loc in relevant_locations:
                        if limit and jobs_count >= limit:
                            break

                        loc_slug = loc['slug']
                        print(f"Searching for '{keywords}' in '{loc['name']}' ({loc_slug})...")
                        
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
        await page.goto(url)
        
        # GUARD 1: Check if we are actually on Seek (not blocked)
        if not await page.query_selector('[data-automation="seek"]'):
            print(f"FAILED: Page integrity check failed for {url}. Possible bot detection.")
            return 0

        # Wait for Seek to settle its Redux state
        # Logic: If already settled (isLoading=false) and has data (jobIds or jobsCount), proceed.
        # Otherwise, wait for it to flip-flop.
        try:
            await page.wait_for_function("""
                window.SEEK_REDUX_DATA && 
                window.SEEK_REDUX_DATA.results.isLoading === false
            """, timeout=10000)
        except Exception:
            print(f"Timeout waiting for Seek state to settle on {url}")

        # Extract Redux data for advanced filtering and discovery
        redux = await page.evaluate("window.SEEK_REDUX_DATA")
        results = redux.get('results', {})
        
        # GUARD 2: Handle Seek search errors
        if results.get('isError'):
            print(f"Seek reported a search error for {url}")
            return 0

        # GUARD 3: Fast-fail if zero results (using Redux state)
        jobs_count_total = redux.get('results', {}).get('totalCount', 0)
        if jobs_count_total == 0:
            # Fallback to SK_DL if Redux results is sparse
            jobs_count_total = await page.evaluate("window.SK_DL ? window.SK_DL.jobsCount : 0")

        if jobs_count_total == 0:
            print(f"Zero results for {url}")
            return 0

        # PRE-FILTER: Check if all IDs on this page are already in DB
        job_ids = results.get('jobIds', [])
        if job_ids:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                placeholders = ','.join(['?'] * len(job_ids))
                cursor.execute(f"SELECT seek_job_id FROM jobs WHERE seek_job_id IN ({placeholders})", job_ids)
                existing_ids = {row['seek_job_id'] for row in cursor.fetchall()}
            
            if len(existing_ids) >= len(job_ids):
                print(f"All {len(job_ids)} jobs on this page are already in the database. Skipping DOM scrape.")
                return 0

        # LOG SUGGESTIONS: Capture related searches for AI discovery
        related = results.get('relatedSearches', [])
        source_keyword = redux.get('results', {}).get('locationWhere', 'Unknown') # or extract from URL
        for item in related:
            self.db.log_suggestion(item.get('keywords'), source_keyword, item.get('totalJobs'))

        # Wait for job cards to load (broad selector)
        try:
            await page.wait_for_selector('[data-automation$="Job"]', timeout=5000)
        except Exception:
            print("No job cards found in DOM after state settlement.")
            return 0
        
        job_cards = await page.query_selector_all('[data-automation$="Job"]')
        print(f"Found {len(job_cards)} job cards in DOM.")
        
        jobs_to_scrape = []
        for card in job_cards:
            if limit and len(jobs_to_scrape) >= limit:
                break

            title_elem = await card.query_selector('[data-automation="jobTitle"]')
            company_elem = await card.query_selector('[data-automation="jobCompany"]')
            location_elem = await card.query_selector('[data-automation="jobLocation"]')
            
            if not title_elem:
                continue
                
            title = await title_elem.inner_text()
            href = await title_elem.get_attribute('href')
            job_url = f"{self.base_url}{href}" if href.startswith('/') else href
            
            # Extract Job ID
            seek_job_id = self._extract_job_id(job_url)
            
            # Clean URL
            job_url = self._clean_url(job_url)
            
            company = await company_elem.inner_text() if company_elem else "Unknown"
            location = await location_elem.inner_text() if location_elem else "Unknown"
            
            # Post-scrape location filter (Defense-in-depth against AU leakage)
            if not self._is_valid_nz_location(location):
                print(f"Skipping out-of-region job: {title} at {location}")
                continue

            # Check if exists in DB by Seek ID
            if self.is_already_scraped(seek_job_id):
                continue
                
            jobs_to_scrape.append({
                "title": title,
                "company": company,
                "location": location,
                "url": job_url,
                "seek_job_id": seek_job_id
            })

        if not jobs_to_scrape:
            return 0

        print(f"Scraping details for {len(jobs_to_scrape)} new jobs concurrently...")
        
        semaphore = asyncio.Semaphore(3)
        
        async def sem_scrape(job):
            async with semaphore:
                print(f"Fetching details for: {job['title']}...")
                raw_text = await self.scrape_job_details(page.context, job['url'])
                if raw_text:
                    self.save_job(job['title'], job['company'], job['location'], job['url'], raw_text, job['seek_job_id'])
                    return True
                return False

        results = await asyncio.gather(*[sem_scrape(j) for j in jobs_to_scrape])
        return sum(1 for r in results if r)

    def _extract_job_id(self, url):
        """Extract the unique integer ID from Seek URL."""
        match = re.search(r'/job/(\d+)', url)
        if match:
            return match.group(1)
        return None

    def _clean_url(self, url):
        """Strip tracking parameters from URL."""
        if '?' in url:
            return url.split('?')[0]
        return url

    def _is_valid_nz_location(self, location_text):
        """Defense-in-depth: Ensure the location is not in Australia."""
        au_indicators = [
            "VIC", "NSW", "QLD", "WA", "SA", "TAS", "NT", "ACT",
            "Melbourne", "Sydney", "Brisbane", "Perth", "Adelaide", "Hobart", "Canberra", "Darwin",
            "Southbank", "Footscray", "Australia"
        ]
        
        for indicator in au_indicators:
            # Use word boundaries to avoid false positives (e.g., "WA" in "Waikato")
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
            details_elem = await page.query_selector('[data-automation="jobAdDetails"]')
            if details_elem:
                return await details_elem.inner_text()
        except Exception as e:
            print(f"Error scraping details for {url}: {e}")
        finally:
            await page.close()
        return None

    def save_job(self, title, company, location, url, raw_text, seek_job_id):
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO jobs (job_title, company, location, url, raw_text, status, seek_job_id)
                    VALUES (?, ?, ?, ?, ?, 'new', ?)
                ''', (title, company, location, url, raw_text, seek_job_id))
                conn.commit()
                self.db.log_action("scrape", f"Saved job: {title} at {company} (ID: {seek_job_id})")
            except sqlite3.IntegrityError:
                pass # Double check for race conditions

if __name__ == "__main__":
    config = load_config()
    db_manager = DatabaseManager()
    collector = SeekCollector(db_manager, config)
    asyncio.run(collector.scrape())
