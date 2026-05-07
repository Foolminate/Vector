from src.database import DatabaseManager
from src.config_loader import load_config
from src.sorter import TriageSorter
from src.collector import SeekCollector
import os
import sqlite3
import pytest
import yaml
from unittest.mock import MagicMock, patch

@pytest.fixture
def test_db(tmp_path):
    db_path = str(tmp_path / "test.db")
    db = DatabaseManager(db_path)
    yield db

def test_collector_save_job(test_db):
    collector = SeekCollector(test_db, {})
    
    # Test saving a new job
    collector.save_job("DevOps Engineer", "Cloud Solutions", "Waikato", "https://example.com/job/123", "Experience with AWS...", "123")
    
    with test_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT job_title, status, seek_job_id FROM jobs WHERE seek_job_id = ?", ("123",))
        row = cursor.fetchone()
        assert row is not None
        assert row['job_title'] == "DevOps Engineer"
        assert row['status'] == "new"
        assert row['seek_job_id'] == "123"
    
    # Test duplicate prevention by Seek ID (should not crash)
    collector.save_job("DevOps Engineer", "Cloud Solutions", "Waikato", "https://example.com/job/123?different_params", "Experience with AWS...", "123")
    with test_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT count(*) FROM jobs WHERE seek_job_id = ?", ("123",))
        assert cursor.fetchone()[0] == 1

def test_triage_thresholds(test_db):
    sorter = TriageSorter(test_db)
    
    # Mock data
    with test_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO jobs (job_title, status) VALUES ('Test Job', 'new')")
        job_id = cursor.lastrowid
        conn.commit()

    # Test High-Pass
    sorter.update_job_status(job_id, {"score": 85, "rationale": "Great"})
    with test_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM jobs WHERE id = ?", (job_id,))
        assert cursor.fetchone()[0] == "high-pass"
    
    # Test Edge-Case
    sorter.update_job_status(job_id, {"score": 50, "rationale": "Maybe"})
    with test_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM jobs WHERE id = ?", (job_id,))
        assert cursor.fetchone()[0] == "edge-case"
    
    # Test Rejected
    sorter.update_job_status(job_id, {"score": 20, "rationale": "No"})
    with test_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM jobs WHERE id = ?", (job_id,))
        assert cursor.fetchone()[0] == "discarded"
def test_triage_logic(test_db):
    # Insert a mock job
    with test_db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO jobs (job_title, company, location, raw_text, status)
            VALUES (?, ?, ?, ?, ?)
        ''', ("Software Engineer", "Tech Corp", "Auckland", "Building automation systems", "new"))
        job_id = cursor.lastrowid
        conn.commit()

    # Mock the GenAI client
    with patch('src.llm_client.genai.Client') as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_response = MagicMock()
        mock_response.text = '{"score": 90, "rationale": "High automation focus"}'
        mock_response.usage_metadata.prompt_token_count = 25
        mock_response.usage_metadata.candidates_token_count = 25
        mock_response.usage_metadata.total_token_count = 50
        mock_client.models.generate_content.return_value = mock_response

        # Run triage
        sorter = TriageSorter(test_db)
        sorter.triage_all_new()

        # Check database update
        with test_db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT status, score, analysis_json FROM jobs WHERE id = ?", (job_id,))
            row = cursor.fetchone()
            assert row['status'] == "high-pass"
            assert row['score'] == 90
            assert "High automation focus" in row['analysis_json']

def test_database_initialization(test_db):
    conn = sqlite3.connect(test_db.db_path)
    cursor = conn.cursor()
    
    # Check if tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jobs'")
    assert cursor.fetchone() is not None
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='audit_log'")
    assert cursor.fetchone() is not None
    
    conn.close()

def test_audit_logging(test_db):
    test_db.log_action("test_action", "test_details")
    
    conn = sqlite3.connect(test_db.db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT action, details FROM audit_log WHERE action='test_action'")
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == "test_action"
    assert row[1] == "test_details"
    conn.close()

def test_load_config():
    # This assumes SEARCH_CONFIG.yaml was already created in the previous step
    config = load_config("SEARCH_CONFIG.yaml")
    assert config is not None
    assert "searches" in config
    assert "locations" in config
    
    # Verify specific Hamilton/Waikato/Remote presence as per user requirement
    location_names = [loc['name'] for loc in config['locations']]
    assert "Hamilton" in location_names
    assert "Waikato" in location_names
    assert "Remote" in location_names

def test_doctrine_file_exists():
    assert os.path.exists("DOCTRINE.md")
    with open("DOCTRINE.md", "r") as f:
        content = f.read()
        assert "Scale Indicators" in content
        assert "Toil Indicators" in content
