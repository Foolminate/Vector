import os
import sqlite3
import pytest
from src.database import DatabaseManager
from src.collector import SeekCollector
from src.sorter import TriageSorter
from src.evaluator import JobEvaluator

@pytest.fixture
def test_db(tmp_path):
    db_path = tmp_path / "test.db"
    return str(db_path)

@pytest.fixture
def migrations_dir():
    return "migrations"

def test_v7_schema_migration(test_db, migrations_dir):
    """Verify that migration v7 adds the required columns to the jobs table."""
    db_manager = DatabaseManager(db_path=test_db, migrations_dir=migrations_dir)
    
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(jobs)")
        columns = {row['name'] for row in cursor.fetchall()}
        
    required_columns = {
        'last_checked_at',
        'is_valid',
        'last_decision_by',
        'expiration_date'
    }
    
    for col in required_columns:
        assert col in columns, f"Column {col} missing from jobs table"

def test_collector_sets_expiration_date(test_db, migrations_dir):
    """Verify that SeekCollector.save_job sets a default 30-day expiration date."""
    db_manager = DatabaseManager(db_path=test_db, migrations_dir=migrations_dir)
    config = {'searches': [], 'locations': []}
    collector = SeekCollector(db_manager, config)
    
    collector.save_job("Test Job", "Test Co", "Test Loc", "http://test.com", "Test Text", "12345")
    
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT expiration_date FROM jobs WHERE seek_job_id = '12345'")
        row = cursor.fetchone()
        assert row['expiration_date'] is not None

def test_sorter_sets_decision_by_robot(test_db, migrations_dir):
    """Verify that TriageSorter.update_job_status sets last_decision_by = 'robot'."""
    db_manager = DatabaseManager(db_path=test_db, migrations_dir=migrations_dir)
    with db_manager.get_connection() as conn:
        conn.execute(
            "INSERT INTO jobs (job_title, company, location, url, raw_text, status) VALUES (?, ?, ?, ?, ?, ?)",
            ("Triage Job", "Triage Co", "Loc", "http://triage.com", "Text", "new")
        )
        conn.commit()
        job_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        
    sorter = TriageSorter(db_manager)
    sorter.update_job_status(job_id, {"score": 85, "rationale": "Great"})
    
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT last_decision_by, status FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        assert row['last_decision_by'] == 'robot'
        assert row['status'] == 'high-pass'

def test_evaluator_sets_decision_by_robot(test_db, migrations_dir):
    """Verify that JobEvaluator.save_evaluation sets last_decision_by = 'robot'."""
    db_manager = DatabaseManager(db_path=test_db, migrations_dir=migrations_dir)
    with db_manager.get_connection() as conn:
        conn.execute(
            "INSERT INTO jobs (job_title, company, location, url, raw_text, status) VALUES (?, ?, ?, ?, ?, ?)",
            ("Eval Job", "Eval Co", "Loc", "http://eval.com", "Text", "high-pass")
        )
        conn.commit()
        job_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        
    evaluator = JobEvaluator(db_manager)
    evaluator.save_evaluation(job_id, {"verdict": "shortlisted", "technical_depth": "High"})
    
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT last_decision_by, status FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        assert row['last_decision_by'] == 'robot'
        assert row['status'] == 'shortlisted'
