import sqlite3
import os
import pytest
from src.database import JobRepository

@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_vector.db")

import shutil

def test_migration_v10_schema_updates(db_path, tmp_path):
    # Setup: Create a temporary migrations directory
    temp_migrations = tmp_path / "migrations"
    temp_migrations.mkdir()
    
    # Copy all real migrations EXCEPT v10
    for f in os.listdir("migrations"):
        if f != "v10_robustness_foundation.sql":
            shutil.copy(os.path.join("migrations", f), temp_migrations)
            
    # 1. Simulate state before v10
    repo = JobRepository(db_path=db_path, migrations_dir=str(temp_migrations))
    
    with repo.get_connection() as conn:
        conn.execute("""
            INSERT INTO jobs (job_title, company, status, rationale, seek_job_id) 
            VALUES ('Old Job', 'Old Co', 'rejected', 'This is a rationale', 'seek_123')
        """)
        conn.commit()
    
    # 2. Add v10 migration file to temp directory
    v10_content = """
-- Migration: v10_robustness_foundation.sql
-- 1. Unify rationale into analysis_json
UPDATE jobs SET analysis_json = json_object('rationale', rationale) 
WHERE rationale IS NOT NULL AND (analysis_json IS NULL OR analysis_json = '');

-- 2. Add performance indices
CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_seek_job_id ON jobs(seek_job_id);

-- 3. Standardize status (rejected -> discarded)
UPDATE jobs SET status = 'discarded' WHERE status = 'rejected';
"""
    v10_path = temp_migrations / "v10_robustness_foundation.sql"
    with open(v10_path, "w") as f:
        f.write(v10_content)
        
    # 3. Re-init repo to trigger v10
    repo.init_db()
    
    with repo.get_connection() as conn:
        # Check status update
        row = conn.execute("SELECT status, analysis_json, rationale FROM jobs WHERE seek_job_id = 'seek_123'").fetchone()
        assert row['status'] == 'discarded'
        assert 'rationale' in row['analysis_json']
        
        # Check index exists
        cursor = conn.execute("PRAGMA index_list('jobs')")
        indices = [r['name'] for r in cursor.fetchall()]
        assert 'idx_jobs_created_at' in indices

def test_job_repository_uses_discarded(db_path):
    repo = JobRepository(db_path=db_path)
    
    # Insert job first
    repo.upsert_job({'title': 'Test Job', 'seek_job_id': 'seek_456'})
    
    # Verify mark_triage_complete uses discarded
    repo.mark_triage_complete('seek_456', 20, "Low score analysis")
    
    with repo.get_connection() as conn:
        row = conn.execute("SELECT status FROM jobs WHERE seek_job_id = 'seek_456'").fetchone()
        assert row['status'] == 'discarded'
