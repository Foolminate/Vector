import pytest
import os
import yaml
from src.config_loader import AppConfig
from src.database import JobRepository, DatabaseManager

def test_app_config_load(tmp_path):
    """Test that AppConfig loads from YAML and handles overrides."""
    config_file = tmp_path / "SEARCH_CONFIG.yaml"
    config_data = {
        "searches": [{"keywords": "Python", "priority": 1}],
        "locations": [{"name": "Hamilton", "slug": "hamilton", "priority": 1}],
        "ai_models": {"sorter": "test-sorter", "evaluator": "test-evaluator"}
    }
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)
    
    # Test file loading
    config = AppConfig.load(str(config_file))
    assert config.searches[0].keywords == "Python"
    assert config.ai_models.sorter == "test-sorter"
    
    # Test env override
    os.environ["VECTOR_AI_MODELS__SORTER"] = "env-sorter"
    config = AppConfig.load(str(config_file))
    assert config.ai_models.sorter == "env-sorter"
    del os.environ["VECTOR_AI_MODELS__SORTER"]

@pytest.fixture
def test_db(tmp_path):
    db_path = tmp_path / "test_vector.db"
    return str(db_path)

def test_job_repository_init_and_migration(test_db):
    """Test that JobRepository initializes and runs migrations."""
    repo = JobRepository(db_path=test_db)
    # Check if a table from a migration exists
    with repo.get_connection() as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'")
        assert cursor.fetchone() is not None
        
        # Check if v8 migration column exists
        cursor = conn.execute("PRAGMA table_info(jobs)")
        columns = [row['name'] for row in cursor.fetchall()]
        assert 'processing_status' in columns

def test_job_repository_state_transitions(test_db):
    """Test that mark_triage_complete follows the state machine rules."""
    repo = JobRepository(db_path=test_db)
    
    # Helper to upsert a dummy job
    job_id = "test-job-1"
    repo.upsert_job({
        "id": job_id,
        "title": "Test Job",
        "company": "Test Co",
        "location": "Test Loc",
        "url": "http://test.com",
        "raw_html": "..."
    })
    
    # 80+ -> high-pass
    repo.mark_triage_complete(job_id, score=85, analysis={"reason": "Good"})
    with repo.get_connection() as conn:
        row = conn.execute("SELECT status FROM jobs WHERE seek_job_id=?", (job_id,)).fetchone()
        assert row['status'] == 'high-pass'
        
    # 40-79 -> edge-case
    job_id_2 = "test-job-2"
    repo.upsert_job({"id": job_id_2, "title": "Edge Job", "company": "Co", "location": "Loc", "url": "url2", "raw_html": "..."})
    repo.mark_triage_complete(job_id_2, score=60, analysis={"reason": "Maybe"})
    with repo.get_connection() as conn:
        row = conn.execute("SELECT status FROM jobs WHERE seek_job_id=?", (job_id_2,)).fetchone()
        assert row['status'] == 'edge-case'
        
    # < 40 -> discarded
    job_id_3 = "test-job-3"
    repo.upsert_job({"id": job_id_3, "title": "Bad Job", "company": "Co", "location": "Loc", "url": "url3", "raw_html": "..."})
    repo.mark_triage_complete(job_id_3, score=20, analysis={"reason": "Bad"})
    with repo.get_connection() as conn:
        row = conn.execute("SELECT status FROM jobs WHERE seek_job_id=?", (job_id_3,)).fetchone()
        assert row['status'] == 'discarded'

def test_database_manager_legacy_wrapper(test_db):
    """Test that DatabaseManager still works as a wrapper around JobRepository."""
    mgr = DatabaseManager(db_path=test_db)
    # It should have inherited or wrapped methods
    mgr.log_action("legacy_test", "details")
    with mgr.get_connection() as conn:
        row = conn.execute("SELECT * FROM audit_log WHERE action='legacy_test'").fetchone()
        assert row['details'] == 'details'
