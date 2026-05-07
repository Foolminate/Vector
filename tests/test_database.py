import pytest
import concurrent.futures
import time
from src.database import JobRepository
from src.models import RawJobData

@pytest.fixture
def repo(tmp_path):
    db_path = tmp_path / "test_vector.db"
    return JobRepository(db_path=str(db_path), migrations_dir="migrations")

def test_concurrent_same_job_upsert(repo):
    """Verify that multiple threads upserting the same job ID don't crash or corrupt data."""
    job_id = "concurrent_1"
    
    def worker(i):
        job = RawJobData(
            title=f"Title {i}",
            company="Co",
            location="Loc",
            url=f"https://nz.seek.com/job/{job_id}",
            seek_job_id=job_id,
            raw_text=f"Description {i}"
        )
        repo.upsert_job(job)
        return i

    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(worker, i) for i in range(20)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    assert len(results) == 20
    
    with repo.get_connection() as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM jobs WHERE seek_job_id = ?", (job_id,))
        count = cursor.fetchone()[0]
        assert count == 1
        
        # Audit log should have multiple entries
        cursor = conn.execute("SELECT COUNT(*) FROM audit_log WHERE details LIKE ?", (f"%{job_id}%",))
        log_count = cursor.fetchone()[0]
        assert log_count == 20

def test_concurrent_status_updates(repo):
    """Verify concurrent status updates to different jobs."""
    # Seed 10 jobs
    for i in range(10):
        repo.upsert_job({
            "id": f"job_{i}",
            "title": f"Job {i}",
            "company": "Co",
            "url": f"http://test.com/{i}",
            "seek_job_id": f"job_{i}"
        })
        
    def worker(i):
        repo.update_job_status(f"job_{i}", "edge-case")
        return i

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        results = list(executor.map(worker, range(10)))

    assert len(results) == 10
    
    with repo.get_connection() as conn:
        cursor = conn.execute("SELECT COUNT(*) FROM jobs WHERE status = 'edge-case'")
        assert cursor.fetchone()[0] == 10

def test_get_pending_triage(repo):
    """Verify fetching jobs pending triage."""
    repo.upsert_job({"title": "Job 1", "url": "url1", "seek_job_id": "1"})
    repo.upsert_job({"title": "Job 2", "url": "url2", "seek_job_id": "2"})
    
    pending = repo.get_pending_triage()
    assert len(pending) == 2
    assert pending[0]['job_title'] == "Job 1"

def test_mark_triage_complete_scoring(repo):
    """Verify status mapping in mark_triage_complete."""
    repo.upsert_job({"title": "Job", "url": "url", "seek_job_id": "job1"})
    
    # High-pass
    repo.mark_triage_complete("job1", 85, {"rationale": "good"})
    with repo.get_connection() as conn:
        row = conn.execute("SELECT status FROM jobs WHERE seek_job_id = 'job1'").fetchone()
        assert row['status'] == 'high-pass'
        
    # Edge-case
    repo.mark_triage_complete("job1", 50, {"rationale": "maybe"})
    with repo.get_connection() as conn:
        row = conn.execute("SELECT status FROM jobs WHERE seek_job_id = 'job1'").fetchone()
        assert row['status'] == 'edge-case'
        
    # Discarded
    repo.mark_triage_complete("job1", 20, {"rationale": "bad"})
    with repo.get_connection() as conn:
        row = conn.execute("SELECT status FROM jobs WHERE seek_job_id = 'job1'").fetchone()
        assert row['status'] == 'discarded'

def test_add_note(repo):
    """Verify adding human notes."""
    repo.upsert_job({"title": "Job", "url": "url", "seek_job_id": "job1"})
    repo.add_note("job1", "Excellent job")
    
    with repo.get_connection() as conn:
        row = conn.execute("SELECT notes, last_decision_by FROM jobs WHERE seek_job_id = 'job1'").fetchone()
        assert row['notes'] == "Excellent job"
        assert row['last_decision_by'] == 'human'
    
    # Test with internal ID too
    with repo.get_connection() as conn:
        internal_id = conn.execute("SELECT id FROM jobs WHERE seek_job_id = 'job1'").fetchone()[0]
    repo.add_note(internal_id, "Internal note")
    with repo.get_connection() as conn:
        row = conn.execute("SELECT notes FROM jobs WHERE id = ?", (internal_id,)).fetchone()
        assert row['notes'] == "Internal note"

def test_mark_evaluation_complete_variants(repo):
    """Verify different variants of mark_evaluation_complete."""
    repo.upsert_job({"title": "Job", "url": "url", "seek_job_id": "job1"})
    
    # Variant 1: Pydantic model and no score
    class MockModel:
        def model_dump(self): return {"pros": ["p"], "cons": ["c"], "verdict": "shortlisted"}
    
    repo.mark_evaluation_complete("job1", MockModel(), "shortlisted")
    with repo.get_connection() as conn:
        row = conn.execute("SELECT status, score FROM jobs WHERE seek_job_id = 'job1'").fetchone()
        assert row['status'] == 'shortlisted'
        assert row['score'] is None
    
    # Variant 2: Dict and score
    repo.mark_evaluation_complete("job1", {"p": 1}, "discarded", score=10)
    with repo.get_connection() as conn:
        row = conn.execute("SELECT status, score FROM jobs WHERE seek_job_id = 'job1'").fetchone()
        assert row['status'] == 'discarded'
        assert row['score'] == 10

def test_upsert_job_dict_variant(repo):
    """Verify upsert_job with a dict that doesn't need much mapping."""
    data = {
        "job_title": "Dict Job",
        "company": "Co",
        "location": "Loc",
        "url": "http://dict.com",
        "raw_text": "Text",
        "id": "dict_1" # mapped to seek_job_id
    }
    repo.upsert_job(data)
    with repo.get_connection() as conn:
        row = conn.execute("SELECT * FROM jobs WHERE seek_job_id = 'dict_1'").fetchone()
        assert row['job_title'] == "Dict Job"

def test_reset_for_evaluation(repo):
    """Verify resetting job status."""
    repo.upsert_job({"title": "Job", "url": "url", "seek_job_id": "job1"})
    repo.update_job_status("job1", "discarded")
    
    repo.reset_for_evaluation("job1")
    with repo.get_connection() as conn:
        row = conn.execute("SELECT status, processing_status FROM jobs WHERE seek_job_id = 'job1'").fetchone()
        assert row['status'] == 'high-pass'
        assert row['processing_status'] == 'idle'

def test_log_cost_and_audit(repo):
    """Verify cost and audit logging."""
    repo.log_cost("gpt-4", 100, 200, 0.01, task="test")
    repo.log_action("test_action", "details")
    
    with repo.get_connection() as conn:
        cost_row = conn.execute("SELECT * FROM cost_log").fetchone()
        assert cost_row['model'] == "gpt-4"
        assert cost_row['cost'] == 0.01
        
        audit_row = conn.execute("SELECT * FROM audit_log WHERE action = 'test_action'").fetchone()
        assert audit_row['details'] == "details"
