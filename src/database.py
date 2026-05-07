import sqlite3
import os
import json
from contextlib import contextmanager
from typing import List, Optional, Union
from .migration_runner import MigrationRunner
from .models import RawJobData

class JobRepository:
    """
    Deep Module for Job domain persistence and state transitions.
    Hides all SQL and lifecycle logic.
    """
    def __init__(self, db_path="data/vector.db", migrations_dir="migrations"):
        self.db_path = db_path
        self.migrations_dir = migrations_dir
        self.init_db()

    @contextmanager
    def get_connection(self):
        """Context manager for SQLite connections with robust defaults."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            yield conn
        finally:
            conn.close()

    def init_db(self):
        """Initialize database using migration runner."""
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir)
            
        runner = MigrationRunner(self.db_path, self.migrations_dir)
        runner.run()

    def upsert_job(self, job_data: Union[dict, RawJobData]):
        """
        Upsert a job and log the action atomically.
        Uses seek_job_id as the primary unique key for external jobs.
        """
        if isinstance(job_data, RawJobData):
            job_dict = job_data.model_dump()
            job_dict['url'] = str(job_dict['url']) # HttpUrl to str
        else:
            job_dict = job_data

        title = job_dict.get('title') or job_dict.get('job_title')
        company = job_dict.get('company')
        location = job_dict.get('location')
        url = job_dict.get('url')
        raw_text = job_dict.get('raw_text') or job_dict.get('raw_html')
        seek_job_id = job_dict.get('seek_job_id') or job_dict.get('id')
        exp_date = job_dict.get('expiration_date')

        with self.get_connection() as conn:
            # 1. Upsert Job
            if exp_date:
                conn.execute('''
                    INSERT INTO jobs (
                        job_title, company, location, url, raw_text, status, seek_job_id, expiration_date
                    ) VALUES (?, ?, ?, ?, ?, 'new', ?, ?)
                    ON CONFLICT(seek_job_id) DO UPDATE SET
                        job_title = excluded.job_title,
                        company = excluded.company,
                        location = excluded.location,
                        url = excluded.url,
                        raw_text = excluded.raw_text
                ''', (title, company, location, url, raw_text, seek_job_id, exp_date))
            else:
                conn.execute('''
                    INSERT INTO jobs (
                        job_title, company, location, url, raw_text, status, seek_job_id, expiration_date
                    ) VALUES (?, ?, ?, ?, ?, 'new', ?, datetime('now', '+30 days'))
                    ON CONFLICT(seek_job_id) DO UPDATE SET
                        job_title = excluded.job_title,
                        company = excluded.company,
                        location = excluded.location,
                        url = excluded.url,
                        raw_text = excluded.raw_text
                ''', (title, company, location, url, raw_text, seek_job_id))
            
            # 2. Log Action
            conn.execute(
                'INSERT INTO audit_log (action, details) VALUES (?, ?)',
                ("scrape", f"Saved/Updated job: {title} at {company} (ID: {seek_job_id})")
            )
            conn.commit()

    def get_pending_triage(self, limit=50):
        """Get jobs with 'new' status that haven't been evaluated yet."""
        with self.get_connection() as conn:
            cursor = conn.execute('''
                SELECT * FROM jobs 
                WHERE status = 'new' 
                AND (is_valid = 1 OR is_valid IS NULL)
                LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def mark_triage_complete(self, job_id, score, analysis, decision_by='robot'):
        """
        Updates job status based on score:
        - 80+ -> high-pass
        - 40-79 -> edge-case
        - < 40 -> discarded
        """
        status = 'discarded'
        if score >= 80:
            status = 'high-pass'
        elif score >= 40:
            status = 'edge-case'
            
        analysis_str = json.dumps(analysis) if isinstance(analysis, (dict, list)) else analysis
        
        with self.get_connection() as conn:
            conn.execute('''
                UPDATE jobs SET 
                    status = ?, 
                    score = ?, 
                    analysis_json = ?, 
                    evaluated_at = CURRENT_TIMESTAMP,
                    last_decision_by = ?
                WHERE seek_job_id = ? OR id = ?
            ''', (status, score, analysis_str, decision_by, job_id, job_id))
            
            # Atomic Audit Log
            conn.execute(
                "INSERT INTO audit_log (action, details) VALUES (?, ?)",
                ("triage", f"Job {job_id} scored {score} -> {status} by {decision_by}")
            )
            conn.commit()

    def update_job_status(self, job_id, status, decision_by='human'):
        """Update job status and tracker who made the decision."""
        with self.get_connection() as conn:
            conn.execute('''
                UPDATE jobs SET 
                    status = ?, 
                    last_decision_by = ?
                WHERE seek_job_id = ? OR id = ?
            ''', (status, decision_by, job_id, job_id))
            conn.commit()

    def update_processing_status(self, job_id, processing_status):
        """Update the background processing status of a job (e.g., 'idle', 'processing', 'failed-permanent')."""
        with self.get_connection() as conn:
            conn.execute('''
                UPDATE jobs SET processing_status = ?
                WHERE seek_job_id = ? OR id = ?
            ''', (processing_status, job_id, job_id))
            conn.commit()

    def delete_job(self, job_id):
        """Hard delete a job from the repository."""
        with self.get_connection() as conn:
            conn.execute('DELETE FROM jobs WHERE seek_job_id = ? OR id = ?', (job_id, job_id))
            conn.commit()

    def add_note(self, job_id, note):
        """Add a manual human note to a job."""
        with self.get_connection() as conn:
            conn.execute('''
                UPDATE jobs SET notes = ?, last_decision_by = 'human'
                WHERE seek_job_id = ? OR id = ?
            ''', (note, job_id, job_id))
            conn.commit()

    def mark_evaluation_complete(self, job_id, analysis, verdict, score=None, decision_by='robot'):
        """
        Saves deep qualitative analysis and updates status.
        Ensures analysis is saved even if rejected.
        """
        if hasattr(analysis, 'model_dump'):
            analysis = analysis.model_dump()
            
        analysis_str = json.dumps(analysis) if isinstance(analysis, (dict, list)) else analysis
        
        with self.get_connection() as conn:
            if score is not None:
                conn.execute('''
                    UPDATE jobs SET 
                        status = ?, 
                        score = ?, 
                        analysis_json = ?, 
                        evaluated_at = CURRENT_TIMESTAMP,
                        last_decision_by = ?
                    WHERE seek_job_id = ? OR id = ?
                ''', (verdict, score, analysis_str, decision_by, job_id, job_id))
            else:
                conn.execute('''
                    UPDATE jobs SET 
                        status = ?, 
                        analysis_json = ?, 
                        evaluated_at = CURRENT_TIMESTAMP,
                        last_decision_by = ?
                    WHERE seek_job_id = ? OR id = ?
                ''', (verdict, analysis_str, decision_by, job_id, job_id))
            
            # Atomic Audit Log
            conn.execute(
                "INSERT INTO audit_log (action, details) VALUES (?, ?)",
                ("evaluation", f"Job {job_id} evaluated -> {verdict} by {decision_by}")
            )
            conn.commit()

    def reset_for_evaluation(self, job_id):
        """
        Resets a job's status to trigger re-evaluation by Agent 2.
        Used for the 'Force Evaluate' feature in TUI.
        """
        with self.get_connection() as conn:
            # We set it to 'high-pass' which is the trigger for Agent 2
            conn.execute('''
                UPDATE jobs SET status = 'high-pass', processing_status = 'idle'
                WHERE seek_job_id = ? OR id = ?
            ''', (job_id, job_id))
            conn.commit()

    def log_action(self, action, details=None):
        """Audit logging for system actions."""
        with self.get_connection() as conn:
            conn.execute('INSERT INTO audit_log (action, details) VALUES (?, ?)', (action, details))
            conn.commit()

    def log_cost(self, model, tokens_in, tokens_out, cost, task=None):
        """Track LLM costs."""
        with self.get_connection() as conn:
            conn.execute('''
                INSERT INTO cost_log (model, tokens_in, tokens_out, cost, task, token_count)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (model, tokens_in, tokens_out, cost, task, tokens_in + tokens_out))
            conn.commit()

    def log_suggestion(self, keywords, source_keyword, total_jobs):
        # ... (unchanged)
        pass

    def archive_and_purge(self):
        """
        Two-stage data retention lifecycle:
        1. Archive: Jobs > 30 days old are marked as 'archived'.
        2. Purge: Jobs > 90 days old are hard-deleted.
        """
        with self.get_connection() as conn:
            # 1. Archive jobs > 30 days (that aren't already archived or shortlisted)
            # Shortlisted jobs are kept active for human review.
            conn.execute('''
                UPDATE jobs 
                SET status = 'archived' 
                WHERE created_at < datetime('now', '-30 days') 
                AND status NOT IN ('archived', 'shortlisted')
            ''')
            
            # 2. Hard-delete jobs > 90 days
            # First, find the seek_job_ids to clean up audit logs
            cursor = conn.execute("SELECT seek_job_id FROM jobs WHERE created_at < datetime('now', '-90 days')")
            ids_to_purge = [row['seek_job_id'] for row in cursor.fetchall() if row['seek_job_id']]
            for seek_id in ids_to_purge:
                conn.execute("DELETE FROM audit_log WHERE details LIKE ?", (f"%{seek_id}%",))
                
            conn.execute("DELETE FROM jobs WHERE created_at < datetime('now', '-90 days')")
            
            conn.execute(
                "INSERT INTO audit_log (action, details) VALUES (?, ?)",
                ("maintenance", f"Retention run complete. Purged {len(ids_to_purge)} jobs.")
            )
            conn.commit()

class DatabaseManager(JobRepository):
    """
    Legacy Wrapper around JobRepository to maintain compatibility 
    with existing modules (review_tui.py, etc.).
    """
    pass
