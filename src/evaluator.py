import json
import os
import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

# Local imports
from .database import DatabaseManager
from .config_loader import load_config
from .llm_client import LLMClient

class JobEvaluation(BaseModel):
    verdict: str = Field(..., pattern="^(shortlisted|discarded)$")
    technical_depth: str
    architectural_opportunities: List[str]
    red_flags: List[str]
    remote_status: str

class JobEvaluator:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        
        config = load_config()
        model_id = config.get('ai_models', {}).get('evaluator', 'gemini-3.1-pro-preview')
        self.llm = LLMClient(db_manager, model_id)

    def evaluate_all_new(self):
        with self.db.get_connection() as conn:
            query = "SELECT id, job_title, company, location, raw_text FROM jobs WHERE status = 'high-pass' AND analysis_json IS NULL"
            cursor = conn.execute(query)
            high_pass_jobs = cursor.fetchall()

        if not high_pass_jobs:
            print("No new high-pass jobs to evaluate.")
            return

        print(f"Starting deep evaluation for {len(high_pass_jobs)} jobs...")

        for job in high_pass_jobs:
            print(f"Evaluating: {job['job_title']} at {job['company']}...")
            result = self.evaluate_job(job['id'], job['job_title'], job['company'], job['location'], job['raw_text'])
            if result:
                data = result.model_dump() if hasattr(result, 'model_dump') else result
                self.save_evaluation(job['id'], data)

    def evaluate_job(self, job_id: int, title: str, company: str, location: str, text: str) -> Optional[JobEvaluation]:
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

Return your response in strict JSON format.
"""
        try:
            return self.llm.generate_json(prompt, response_model=JobEvaluation, task="evaluation", job_id=job_id)
        except Exception as e:
            print(f"Error evaluating job {job_id}: {e}")
            return None

    def save_evaluation(self, job_id: int, result: Dict[str, Any]):
        status = result.get("verdict", "analyzed")
        self.db.mark_evaluation_complete(job_id, result, status)
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
