import pytest
import sqlite3
import datetime
from src.database import DatabaseManager
from src.digest_manager import DigestManager

@pytest.fixture
def db_manager(tmp_path):
    db_path = str(tmp_path / "test_digest.db")
    db = DatabaseManager(db_path)
    
    # Seed some data with different evaluation dates
    with db.get_connection() as conn:
        # Date 1: 2024-05-01
        conn.execute('''
            INSERT INTO jobs (job_title, company, location, score, status, analysis_json, evaluated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ("Job 1", "Company A", "Hamilton", 90, "analyzed", 
              '{"technical_depth": "Deep", "remote_status": "Verified", "architectural_opportunities": ["Opp 1"]}', 
              '2024-05-01 10:00:00'))
        
        # Date 2: 2024-05-02
        conn.execute('''
            INSERT INTO jobs (job_title, company, location, score, status, analysis_json, evaluated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', ("Job 2", "Company B", "Remote", 85, "analyzed", 
              '{"technical_depth": "Moderate", "remote_status": "Likely"}', 
              '2024-05-02 12:00:00'))
        
        conn.commit()
    return db

def test_get_available_dates(db_manager):
    """Verify that we can get a list of unique dates where evaluations occurred."""
    manager = DigestManager(db_manager)
    dates = manager.get_available_dates()
    
    assert "2024-05-01" in dates
    assert "2024-05-02" in dates
    assert len(dates) == 2

def test_render_digest(db_manager):
    """Verify that a digest for a specific date is rendered correctly as Markdown."""
    manager = DigestManager(db_manager)
    markdown = manager.render_digest("2024-05-01")
    
    assert "# Project Vector: Architectural Opportunity Digest" in markdown
    assert "2024-05-01" in markdown
    assert "Job 1" in markdown
    assert "Company A" in markdown
    assert "Opp 1" in markdown
    assert "Job 2" not in markdown  # Should only contain jobs from that date
