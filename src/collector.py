import asyncio
import random
import sqlite3
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

# Local imports
from .config_loader import load_config
from .database import DatabaseManager

class SeekCollector:
    def __init__(self, db_manager: DatabaseManager, config: dict):
        self.db = db_manager
        self.config = config
        self.base_url = "https://www.seek.co.nz"
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

                        loc_id = loc['id']
                        print(f"Searching for '{keywords}' in '{loc['name']}' ({loc_id})...")
                        
                        search_url = f"{self.base_url}/jobs?keywords={keywords.replace(' ', '%20')}&where={loc_id}"
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
        # Wait for job cards to load
        try:
            await page.wait_for_selector('[data-automation="normalJob"]', timeout=10000)
        except Exception:
            print("No job cards found on this page.")
            return 0
        
        job_cards = await page.query_selector_all('[data-automation="normalJob"]')
        print(f"Found {len(job_cards)} job cards.")
        
        jobs_added = 0
        for card in job_cards:
            if limit and jobs_added >= limit:
                break

            title_elem = await card.query_selector('[data-automation="jobTitle"]')
            company_elem = await card.query_selector('[data-automation="jobCompany"]')
            location_elem = await card.query_selector('[data-automation="jobLocation"]')
            
            if not title_elem:
                continue
                
            title = await title_elem.inner_text()
            href = await title_elem.get_attribute('href')
            job_url = f"{self.base_url}{href}" if href.startswith('/') else href
            
            company = await company_elem.inner_text() if company_elem else "Unknown"
            location = await location_elem.inner_text() if location_elem else "Unknown"
            
            # Check if exists in DB
            if self.is_already_scraped(job_url):
                continue
                
            print(f"New job found: {title} at {company}")
            
            # Scrape details
            raw_text = await self.scrape_job_details(page.context, job_url)
            
            if raw_text:
                self.save_job(title, company, location, job_url, raw_text)
                jobs_added += 1
                if limit and jobs_added >= limit:
                    break
                await asyncio.sleep(random.uniform(1, 3))
        
        return jobs_added

    def is_already_scraped(self, url):
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM jobs WHERE url = ?", (url,))
        result = cursor.fetchone()
        conn.close()
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

    def save_job(self, title, company, location, url, raw_text):
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute('''
                INSERT INTO jobs (job_title, company, location, url, raw_text, status)
                VALUES (?, ?, ?, ?, ?, 'new')
            ''', (title, company, location, url, raw_text))
            conn.commit()
            self.db.log_action("scrape", f"Saved job: {title} at {company}")
        except sqlite3.IntegrityError:
            pass # Double check for race conditions
        finally:
            conn.close()

if __name__ == "__main__":
    config = load_config()
    db_manager = DatabaseManager()
    collector = SeekCollector(db_manager, config)
    asyncio.run(collector.scrape())
