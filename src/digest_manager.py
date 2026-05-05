import json
from typing import List
from .database import DatabaseManager

class DigestManager:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def get_available_dates(self) -> List[str]:
        """Returns a list of unique dates (YYYY-MM-DD) from the evaluated_at column."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            # DATE() function extracts the date part from the timestamp
            cursor.execute("SELECT DISTINCT DATE(evaluated_at) as eval_date FROM jobs WHERE evaluated_at IS NOT NULL ORDER BY eval_date DESC")
            return [row['eval_date'] for row in cursor.fetchall()]

    def render_digest(self, date_str: str) -> str:
        """Generates a Markdown digest for all jobs evaluated on a specific date."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            # Filter by the date part of evaluated_at
            cursor.execute("""
                SELECT * FROM jobs 
                WHERE DATE(evaluated_at) = ? 
                AND analysis_json IS NOT NULL
            """, (date_str,))
            jobs = [dict(row) for row in cursor.fetchall()]

        if not jobs:
            return f"# Project Vector: Architectural Opportunity Digest\n\nNo jobs evaluated on {date_str}."

        # Re-using the priority sorting logic from evaluator.py
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

        lines = [
            f"# Project Vector: Architectural Opportunity Digest",
            f"Evaluation Date: {date_str}",
            ""
        ]

        for job in jobs:
            analysis = json.loads(job['analysis_json'])
            lines.append(f"## {job['job_title']} @ {job['company']}")
            lines.append(f"- **Location:** {job['location']}")
            lines.append(f"- **Score:** {job['score']}")
            lines.append(f"- **Remote:** {analysis.get('remote_status')}")
            lines.append(f"- **URL:** {job['url']}")
            lines.append("")
            
            lines.append(f"### Technical Depth")
            lines.append(f"{analysis.get('technical_depth')}")
            lines.append("")
            
            opps = analysis.get('architectural_opportunities', [])
            if opps:
                lines.append(f"### Architectural Opportunities")
                for opp in opps:
                    lines.append(f"- {opp}")
                lines.append("")
            
            flags = analysis.get('red_flags', [])
            if flags:
                lines.append(f"### Red Flags")
                for flag in flags:
                    lines.append(f"- {flag}")
                lines.append("")
            
            if job.get('notes'):
                lines.append(f"### Human Notes")
                lines.append(f"{job['notes']}")
                lines.append("")

            lines.append("---")
            lines.append("")

        return "\n".join(lines)
