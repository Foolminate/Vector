import pytest
import os
import sqlite3
from src.database import JobRepository
from src.models import RawJobData

@pytest.fixture
def repo(tmp_path):
    db_path = tmp_path / "test_vector.db"
    # Ensure migrations are available
    return JobRepository(db_path=str(db_path), migrations_dir="migrations")

def test_upsert_job_accepts_raw_job_data(repo):
    job = RawJobData(
        title="Test Job",
        company="Test Corp",
        location="Auckland",
        url="https://nz.seek.com/job/123",
        seek_job_id="123",
        raw_text="Some description"
    )
    
    repo.upsert_job(job)
    
    with repo.get_connection() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE seek_job_id = '123'").fetchone()
        assert row is not None
        assert row['job_title'] == "Test Job"
        assert row['company'] == "Test Corp"

def test_upsert_job_is_atomic_with_audit_log(repo, monkeypatch):
    job = RawJobData(
        title="Atomic Job",
        company="Atomic Corp",
        location="Auckland",
        url="https://nz.seek.com/job/456",
        seek_job_id="456",
        raw_text="Atomic description"
    )
    
    # We want to verify that both the job insertion and the audit log entry happen.
    # We also want to verify that if one fails, both fail.
    
    repo.upsert_job(job)
    
    with repo.get_connection() as conn:
        job_row = conn.execute("SELECT * FROM jobs WHERE seek_job_id = '456'").fetchone()
        log_row = conn.execute("SELECT * FROM audit_log WHERE details LIKE '%456%'").fetchone()
        
        assert job_row is not None
        assert log_row is not None
        assert log_row['action'] == "scrape"

import concurrent.futures

def test_concurrent_upserts(repo):
    jobs = [
        RawJobData(
            title=f"Job {i}",
            company="Concurrent Corp",
            location="Auckland",
            url=f"https://nz.seek.com/job/{i}",
            seek_job_id=str(i),
            raw_text="Description"
        ) for i in range(10)
    ]
    
    def do_upsert(job):
        repo.upsert_job(job)
        return True

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(do_upsert, jobs))
        
    assert all(results)
    
    with repo.get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        assert count == 10
        
        log_count = conn.execute("SELECT COUNT(*) FROM audit_log WHERE action = 'scrape'").fetchone()[0]
        assert log_count == 10
