import os
import sqlite3
import pytest
from src.database import DatabaseManager
from src.evaluator import JobEvaluator

from unittest.mock import MagicMock, patch

@pytest.fixture
def db_path(tmp_path):
    return str(tmp_path / "test_evaluated_at.db")

@pytest.fixture
def db_manager(db_path):
    db = DatabaseManager(db_path)
    # Insert a job to evaluate
    with db.get_connection() as conn:
        conn.execute('''
            INSERT INTO jobs (job_title, company, location, raw_text, status, score)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ("Test Job", "Test Co", "Remote", "Test text", "high-pass", 90))
        conn.commit()
    return db

def test_evaluated_at_column_exists(db_path):
    """RED: Verify that evaluated_at column exists in jobs table."""
    db = DatabaseManager(db_path)
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("PRAGMA table_info(jobs)")
        columns = [row['name'] for row in cursor.fetchall()]
        assert "evaluated_at" in columns

def test_save_evaluation_updates_evaluated_at(db_manager):
    """RED: Verify that save_evaluation updates the evaluated_at timestamp."""
    with patch('src.llm_client.genai.Client'):
        evaluator = JobEvaluator(db_manager)
        
        # Verify initial state is NULL
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT evaluated_at FROM jobs WHERE job_title = 'Test Job'")
            assert cursor.fetchone()[0] is None
            
        # Perform save_evaluation
        evaluator.save_evaluation(1, {"technical_depth": "High", "remote_status": "Verified"})
        
        # Verify evaluated_at is now set
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT evaluated_at FROM jobs WHERE job_title = 'Test Job'")
            val = cursor.fetchone()[0]
            assert val is not None
