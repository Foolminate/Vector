import json
import os
import datetime
from typing import Dict, Any, List

# Local imports
from .database import DatabaseManager
from .config_loader import load_config
from .llm_client import LLMClient

class JobEvaluator:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        
        config = load_config()
        model_id = config.get('ai_models', {}).get('evaluator', 'gemini-3.1-pro-preview')
        self.llm = LLMClient(db_manager, model_id)

    def evaluate_all_new(self):
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, job_title, company, location, raw_text FROM jobs WHERE status = 'high-pass' AND analysis_json IS NULL")
            high_pass_jobs = cursor.fetchall()

        if not high_pass_jobs:
            print("No new high-pass jobs to evaluate.")
            return

        print(f"Starting deep evaluation for {len(high_pass_jobs)} jobs...")

        for job_id, title, company, location, text in high_pass_jobs:
            print(f"Evaluating: {title} at {company}...")
            result = self.evaluate_job(job_id, title, company, location, text)
            if result:
                self.save_evaluation(job_id, result)

    def evaluate_job(self, job_id: int, title: str, company: str, location: str, text: str) -> Dict[str, Any]:
        prompt = f"""
You are Agent 2 (The Evaluator) in Project Vector. Your task is to perform a deep qualitative analysis on a high-potential job description.

### Job Details:
- Title: {title}
- Company: {company}
- Location: {location}
- Description: {text}

### Instructions:
Analyze the job for technical depth, architectural opportunities, and potential red flags. Be critical and look for signals of genuine technical impact versus manual toil.

Based on your analysis, provide a verdict:
- "shortlisted": High architectural opportunity, manageable red flags.
- "discarded": Low technical depth or critical red flags (e.g., pure legacy maintenance).

Return your response in strict JSON format:
{{
  "verdict": "shortlisted | discarded",
  "technical_depth": "Summary of technical challenges and impact",
  "architectural_opportunities": ["Opportunity 1", "Opportunity 2"],
  "red_flags": ["Concern 1", "Concern 2"],
  "remote_status": "Verified | Likely | Unlikely"
}}
"""
        try:
            return self.llm.generate_json(prompt, job_id=job_id, action="evaluation")
        except Exception:
            return None

    def save_evaluation(self, job_id: int, result: Dict[str, Any]):
        analysis_json = json.dumps(result)
        status = result.get("verdict", "analyzed")
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE jobs 
                SET analysis_json = ?, evaluated_at = CURRENT_TIMESTAMP, status = ?, last_decision_by = 'robot'
                WHERE id = ?
            ''', (analysis_json, status, job_id))
            conn.commit()
        
        self.db.log_action("evaluation", f"Deep analysis completed for job {job_id}")

    def generate_digest(self, output_dir: str = "digests") -> str:
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        from .digest_manager import DigestManager
        dm = DigestManager(self.db)
        
        # Get the latest evaluation date
        dates = dm.get_available_dates()
        if not dates:
            return None
            
        latest_date = dates[0]
        markdown = dm.render_digest(latest_date)
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"digest_{timestamp}.md"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w') as f:
            f.write(markdown)
        
        # Mark jobs as analyzed (only those evaluated on the latest_date)
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE jobs SET status = 'analyzed' WHERE DATE(evaluated_at) = ?", (latest_date,))
            conn.commit()
        
        return filepath
