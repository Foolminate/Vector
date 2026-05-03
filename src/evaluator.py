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

Return your response in strict JSON format:
{{
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
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE jobs 
                SET analysis_json = ?
                WHERE id = ?
            ''', (analysis_json, job_id))
            conn.commit()
        
        self.db.log_action("evaluation", f"Deep analysis completed for job {job_id}")

    def generate_digest(self, output_dir: str = "digests") -> str:
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            # Fetch all jobs that have analysis_json and are in high-pass status
            cursor.execute("SELECT * FROM jobs WHERE status = 'high-pass' AND analysis_json IS NOT NULL")
            jobs = [dict(row) for row in cursor.fetchall()]
        
        if not jobs:
            return None
            
        # Priority Sorting: Hamilton/Waikato/Remote first
        def priority_score(job):
            location = job['location'].lower()
            analysis = json.loads(job['analysis_json'])
            remote = analysis.get('remote_status', '').lower()
            
            score = 0
            if "hamilton" in location or "waikato" in location:
                score += 10
            if remote == "verified":
                score += 10
            elif remote == "likely":
                score += 5
            return score

        jobs.sort(key=priority_score, reverse=True)
        
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"digest_{timestamp}.md"
        filepath = os.path.join(output_dir, filename)
        
        with open(filepath, 'w') as f:
            f.write(f"# Project Vector: Architectural Opportunity Digest\n")
            f.write(f"Generated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            for job in jobs:
                analysis = json.loads(job['analysis_json'])
                f.write(f"## {job['job_title']} @ {job['company']}\n")
                f.write(f"- **Location:** {job['location']}\n")
                f.write(f"- **Score:** {job['score']}\n")
                f.write(f"- **Remote:** {analysis.get('remote_status')}\n")
                f.write(f"- **URL:** {job['url']}\n\n")
                
                f.write(f"### Technical Depth\n{analysis.get('technical_depth')}\n\n")
                
                f.write(f"### Architectural Opportunities\n")
                for opp in analysis.get('architectural_opportunities', []):
                    f.write(f"- {opp}\n")
                f.write("\n")
                
                if analysis.get('red_flags'):
                    f.write(f"### Red Flags\n")
                    for flag in analysis.get('red_flags', []):
                        f.write(f"- {flag}\n")
                    f.write("\n")
                
                f.write("---\n\n")
        
        # Mark jobs as analyzed
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            for job in jobs:
                cursor.execute("UPDATE jobs SET status = 'analyzed' WHERE id = ?", (job['id'],))
            conn.commit()
        
        return filepath
