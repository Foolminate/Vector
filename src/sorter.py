import os
from typing import Dict, Any

# Local imports
from .database import DatabaseManager
from .config_loader import load_config
from .llm_client import LLMClient

class TriageSorter:
    def __init__(self, db_manager: DatabaseManager, doctrine_path: str = "DOCTRINE.md"):
        self.db = db_manager
        self.doctrine = self._load_doctrine(doctrine_path)
        
        config = load_config()
        model_id = config.get('ai_models', {}).get('sorter', 'gemini-3-flash-preview')
        self.llm = LLMClient(db_manager, model_id)

    def _load_doctrine(self, path: str) -> str:
        if not os.path.exists(path):
            print(f"Warning: Doctrine file {path} not found. Using fallback.")
            return """
            # Standard Triage Doctrine
            - Focus on technical relevance (software, engineering, automation).
            - Prioritize architectural and strategic roles.
            - Filter out manual toil and administrative tasks.
            """
        with open(path, 'r') as f:
            return f.read()

    def triage_all_new(self):
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, job_title, company, location, raw_text FROM jobs WHERE status = 'new'")
            new_jobs = cursor.fetchall()

        if not new_jobs:
            print("No new jobs to triage.")
            return

        print(f"Starting triage for {len(new_jobs)} new jobs...")

        for job_id, title, company, location, text in new_jobs:
            print(f"Triaging: {title} at {company}...")
            result = self.triage_job(job_id, title, company, location, text)
            if result:
                self.update_job_status(job_id, result)

    def triage_job(self, job_id: int, title: str, company: str, location: str, text: str) -> Dict[str, Any]:
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
            return self.llm.generate_json(prompt, job_id=job_id, action="triage")
        except Exception as e:
            print(f"Error triaging job {job_id}: {e}")
            return None

    def update_job_status(self, job_id: int, result: Any):
        if not isinstance(result, dict):
            print(f"Error: Expected dictionary for triage result, got {type(result)}")
            return

        score = result.get('score', 0)
        rationale = result.get('rationale', "No rationale provided")
        
        # Use JobRepository method to standardize logic and status
        self.db.mark_triage_complete(job_id, score, {"rationale": rationale})
        
        # We don't need status local variable here anymore as mark_triage_complete handles it
        # But for logging we can get it if we really wanted to, or just log the score.
        self.db.log_action("triage", f"Job {job_id} scored {score}")

if __name__ == "__main__":
    db_manager = DatabaseManager()
    sorter = TriageSorter(db_manager)
    sorter.triage_all_new()
