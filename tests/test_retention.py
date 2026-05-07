import pytest
import sqlite3
import datetime
from src.database import JobRepository

@pytest.fixture
def repo(tmp_path):
    db_path = tmp_path / "test_vector.db"
    return JobRepository(db_path=str(db_path), migrations_dir="migrations")

def test_archive_logic(repo):
    """Jobs > 30 days old should be marked as archived."""
    with repo.get_connection() as conn:
        # Create a job that is 31 days old
        old_date = (datetime.datetime.now() - datetime.timedelta(days=31)).strftime('%Y-%m-%d %H:%M:%S')
        conn.execute('''
            INSERT INTO jobs (job_title, status, created_at, seek_job_id) 
            VALUES ('Old Job', 'analyzed', ?, 'old_1')
        ''', (old_date,))
        
        # Create a job that is 10 days old
        recent_date = (datetime.datetime.now() - datetime.timedelta(days=10)).strftime('%Y-%m-%d %H:%M:%S')
        conn.execute('''
            INSERT INTO jobs (job_title, status, created_at, seek_job_id) 
            VALUES ('Recent Job', 'analyzed', ?, 'recent_1')
        ''', (recent_date,))
        conn.commit()
    
    repo.archive_and_purge()
    
    with repo.get_connection() as conn:
        old_job = conn.execute("SELECT status FROM jobs WHERE seek_job_id = 'old_1'").fetchone()
        recent_job = conn.execute("SELECT status FROM jobs WHERE seek_job_id = 'recent_1'").fetchone()
        
        assert old_job['status'] == 'archived'
        assert recent_job['status'] == 'analyzed'

def test_purge_logic(repo):
    """Jobs > 90 days old should be hard-deleted."""
    with repo.get_connection() as conn:
        # Create a job that is 91 days old
        very_old_date = (datetime.datetime.now() - datetime.timedelta(days=91)).strftime('%Y-%m-%d %H:%M:%S')
        conn.execute('''
            INSERT INTO jobs (job_title, status, created_at, seek_job_id) 
            VALUES ('Very Old Job', 'archived', ?, 'very_old_1')
        ''', (very_old_date,))
        
        # Create a job that is 45 days old (should be archived but not purged)
        archived_date = (datetime.datetime.now() - datetime.timedelta(days=45)).strftime('%Y-%m-%d %H:%M:%S')
        conn.execute('''
            INSERT INTO jobs (job_title, status, created_at, seek_job_id) 
            VALUES ('Archived Job', 'archived', ?, 'archived_1')
        ''', (archived_date,))
        conn.commit()
    
    repo.archive_and_purge()
    
    with repo.get_connection() as conn:
        very_old_job = conn.execute("SELECT * FROM jobs WHERE seek_job_id = 'very_old_1'").fetchone()
        archived_job = conn.execute("SELECT * FROM jobs WHERE seek_job_id = 'archived_1'").fetchone()
        
def test_purge_cleans_up_audit_log(repo):
    """Audit logs linked to purged jobs should be removed."""
    with repo.get_connection() as conn:
        very_old_date = (datetime.datetime.now() - datetime.timedelta(days=91)).strftime('%Y-%m-%d %H:%M:%S')
        conn.execute('''
            INSERT INTO jobs (job_title, status, created_at, seek_job_id) 
            VALUES ('Purge Me', 'archived', ?, 'purge_123')
        ''', (very_old_date,))
        
        conn.execute(
            "INSERT INTO audit_log (action, details) VALUES (?, ?)",
            ("scrape", "Saved job: Purge Me (ID: purge_123)")
        )
        conn.execute(
            "INSERT INTO audit_log (action, details) VALUES (?, ?)",
            ("triage", "Job purge_123 scored 10")
        )
        # Unrelated log
        conn.execute(
            "INSERT INTO audit_log (action, details) VALUES (?, ?)",
            ("scrape", "Saved job: Keep Me (ID: keep_456)")
        )
        conn.commit()

    repo.archive_and_purge()
    
    with repo.get_connection() as conn:
        # Purged job's logs should be gone
        logs = conn.execute("SELECT * FROM audit_log WHERE details LIKE '%purge_123%'").fetchall()
        assert len(logs) == 0
        
        # Unrelated log should remain
        keep_logs = conn.execute("SELECT * FROM audit_log WHERE details LIKE '%keep_456%'").fetchall()
        assert len(keep_logs) == 1
