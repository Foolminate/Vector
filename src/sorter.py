import json
import os
import sqlite3
from typing import Dict, Any
from google import genai
from google.genai import types

# Local imports
from .database import DatabaseManager

class TriageSorter:
    def __init__(self, db_manager: DatabaseManager, doctrine_path: str = "DOCTRINE.md"):
        self.db = db_manager
        self.doctrine = self._load_doctrine(doctrine_path)
        
        api_key = os.environ.get("GEMINI_VECTOR_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_VECTOR_API_KEY environment variable not set.")
        
        self.client = genai.Client(api_key=api_key)
        # Using gemini-3-flash-preview for cost-optimized triage in 2026
        self.model_id = 'gemini-3-flash-preview'

    def _load_doctrine(self, path: str) -> str:
        with open(path, 'r') as f:
            return f.read()

    def triage_all_new(self):
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, job_title, company, location, raw_text FROM jobs WHERE status = 'new'")
        new_jobs = cursor.fetchall()
        conn.close()

        if not new_jobs:
            print("No new jobs to triage.")
            return

        print(f"Starting triage for {len(new_jobs)} new jobs...")

        for job_id, title, company, location, text in new_jobs:
            print(f"Triaging: {title} at {company}...")
            result = self.triage_job(title, company, location, text)
            if result:
                self.update_job_status(job_id, result)

    def triage_job(self, title: str, company: str, location: str, text: str) -> Dict[str, Any]:
        prompt = f"""
You are Agent 1 (The Sorter) in Project Vector. Your task is to perform rapid triage on a job description based on the provided Technical Doctrine.

### Technical Doctrine:
{self.doctrine}

### Job Details:
- Title: {title}
- Company: {company}
- Location: {location}
- Description: {text}

### Instructions:
Evaluate the job against the Doctrine. Assign a score from 0 to 100.
- High-Pass (>=80): Clearly technical, architectural, or strategic automation focus.
- Edge-Case (40-79): Borderline, requires human review.
- Low-Pass (<40): Purely manual toil, administrative, or accounting/finance focus.

Return your response in strict JSON format:
{{
  "score": integer,
  "rationale": "one-sentence explanation matching the doctrine"
}}
"""
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            return json.loads(response.text)
        except Exception as e:
            print(f"Error triaging job: {e}")
            return None

    def update_job_status(self, job_id: int, result: Dict[str, Any]):
        score = result.get('score', 0)
        rationale = result.get('rationale', "No rationale provided")
        
        status = 'rejected'
        if score >= 80:
            status = 'high-pass'
        elif score >= 40:
            status = 'edge-case'
            
        conn = sqlite3.connect(self.db.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            UPDATE jobs 
            SET status = ?, score = ?, rationale = ?
            WHERE id = ?
        ''', (status, score, rationale, job_id))
        conn.commit()
        conn.close()
        
        self.db.log_action("triage", f"Job {job_id} scored {score} -> {status}")

if __name__ == "__main__":
    db_manager = DatabaseManager()
    sorter = TriageSorter(db_manager)
    sorter.triage_all_new()
