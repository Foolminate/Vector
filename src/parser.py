from bs4 import BeautifulSoup
import json
import re
from typing import List, Optional, Dict
from .models import RawJobData

class SeekParser:
    """
    Pure extraction engine for Seek job data.
    Separates 'fetching' (IO) from 'parsing' (Logic).
    """

    def parse_search_results(self, redux_data: dict, html: str) -> List[RawJobData]:
        """
        Extract job listings from Redux data with DOM fallback.
        """
        # 1. Try Redux (Preferred)
        jobs = self._parse_from_redux(redux_data)
        if jobs:
            return jobs
        
        # 2. Try DOM Fallback
        return self._parse_from_dom(html)

    def _parse_from_redux(self, redux: dict) -> List[RawJobData]:
        if not redux or 'results' not in redux:
            return []
            
        jobs_data = redux.get('results', {}).get('jobs', [])
        if not jobs_data:
            return []
            
        parsed_jobs = []
        for job in jobs_data:
            job_id = job.get('id')
            if not job_id:
                continue
                
            parsed_jobs.append(RawJobData(
                title=job.get('title'),
                company=job.get('advertiser', {}).get('description', 'Unknown'),
                location=job.get('location', 'Unknown'),
                seek_job_id=str(job_id),
                url=f"https://nz.seek.com/job/{job_id}",
                expiration_date=job.get('expiryDate') or job.get('listingExpiryDate')
            ))
        return parsed_jobs

    def _parse_from_dom(self, html: str) -> List[RawJobData]:
        if not html:
            return []
            
        soup = BeautifulSoup(html, 'html.parser')
        # Seek job cards usually have data-automation="jobCard", "normalJob", "premiumJob", etc.
        job_cards = soup.find_all(attrs={"data-automation": re.compile(r"job", re.I)})
        
        parsed_jobs = []
        for card in job_cards:
            title_elem = card.find(attrs={"data-automation": "jobTitle"})
            if not title_elem:
                # If it doesn't have a title, it's probably not a job card (or it's a sub-element)
                continue
                
            title = title_elem.get_text().strip()
            company_elem = card.find(attrs={"data-automation": "jobCompany"})
            company = company_elem.get_text().strip() if company_elem else "Unknown"
            
            location_elem = card.find(attrs={"data-automation": "jobLocation"})
            location = location_elem.get_text().strip() if location_elem else "Unknown"
            
            href = title_elem.get('href', '')
            seek_job_id = card.get('data-job-id') or self._extract_job_id(href)
            
            if not seek_job_id:
                continue

            parsed_jobs.append(RawJobData(
                title=title,
                company=company,
                location=location,
                seek_job_id=str(seek_job_id),
                url=f"https://nz.seek.com/job/{seek_job_id}"
            ))
            
        return parsed_jobs

    def parse_job_details(self, html: str) -> str:
        """Extract job description text from job details page."""
        if not html:
            return ""
        soup = BeautifulSoup(html, 'html.parser')
        details = soup.find(attrs={"data-automation": "jobAdDetails"})
        return details.get_text(separator='\n').strip() if details else ""

    def _extract_job_id(self, url: str) -> Optional[str]:
        match = re.search(r'/job/(\d+)', url)
        return match.group(1) if match else None
