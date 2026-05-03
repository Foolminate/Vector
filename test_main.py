from src.main import DatabaseManager, load_config
from src.sorter import TriageSorter
from src.collector import SeekCollector
import os
import sqlite3
import pytest
import yaml
from unittest.mock import MagicMock, patch

@pytest.fixture
def test_db():
    db_path = "data/test.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    db = DatabaseManager(db_path)
    yield db
    if os.path.exists(db_path):
        os.remove(db_path)

def test_collector_save_job(test_db):
    collector = SeekCollector(test_db, {})
    
    # Test saving a new job
    collector.save_job("DevOps Engineer", "Cloud Solutions", "Waikato", "https://example.com/job1", "Experience with AWS...")
    
    conn = sqlite3.connect(test_db.db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT job_title, status FROM jobs WHERE url = ?", ("https://example.com/job1",))
    row = cursor.fetchone()
    assert row is not None
    assert row[0] == "DevOps Engineer"
    assert row[1] == "new"
    
    # Test duplicate prevention (should not crash)
    collector.save_job("DevOps Engineer", "Cloud Solutions", "Waikato", "https://example.com/job1", "Experience with AWS...")
    cursor.execute("SELECT count(*) FROM jobs WHERE url = ?", ("https://example.com/job1",))
    assert cursor.fetchone()[0] == 1
    conn.close()

def test_triage_thresholds(test_db):
    sorter = TriageSorter(test_db)
    
    # Mock data
    job_id = 1
    conn = sqlite3.connect(test_db.db_path)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO jobs (job_title, status) VALUES ('Test Job', 'new')")
    job_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # Test High-Pass
    sorter.update_job_status(job_id, {"score": 85, "rationale": "Great"})
    conn = sqlite3.connect(test_db.db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM jobs WHERE id = ?", (job_id,))
    assert cursor.fetchone()[0] == "high-pass"
    
    # Test Edge-Case
    sorter.update_job_status(job_id, {"score": 50, "rationale": "Maybe"})
    cursor.execute("SELECT status FROM jobs WHERE id = ?", (job_id,))
    assert cursor.fetchone()[0] == "edge-case"
    
    # Test Rejected
    sorter.update_job_status(job_id, {"score": 20, "rationale": "No"})
    cursor.execute("SELECT status FROM jobs WHERE id = ?", (job_id,))
    assert cursor.fetchone()[0] == "rejected"
    conn.close()

def test_triage_logic(test_db):
    # Insert a mock job
    conn = sqlite3.connect(test_db.db_path)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO jobs (job_title, company, location, raw_text, status)
        VALUES (?, ?, ?, ?, ?)
    ''', ("Software Engineer", "Tech Corp", "Auckland", "Building automation systems", "new"))
    job_id = cursor.lastrowid
    conn.commit()
    conn.close()

    # Mock the GenAI client
    with patch('src.sorter.genai.Client') as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_response = MagicMock()
        mock_response.text = '{"score": 90, "rationale": "High automation focus"}'
        mock_client.models.generate_content.return_value = mock_response

        # Run triage
        sorter = TriageSorter(test_db)
        sorter.triage_all_new()

        # Check database update
        conn = sqlite3.connect(test_db.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT status, score, rationale FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        assert row[0] == "high-pass"
        assert row[1] == 90
        assert row[2] == "High automation focus"
        conn.close()

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
