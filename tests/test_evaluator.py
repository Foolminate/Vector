import os
import sqlite3
import pytest
from unittest.mock import MagicMock, patch
from src.database import DatabaseManager
from src.evaluator import JobEvaluator

@pytest.fixture
def test_db(tmp_path):
    db_path = str(tmp_path / "test_evaluator.db")
    db = DatabaseManager(db_path)
    
    # Insert a high-pass job ready for evaluation
    with db.get_connection() as conn:
        conn.execute('''
            INSERT INTO jobs (job_title, company, location, raw_text, status, score)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', ("Senior Data Architect", "NZ Data Co", "Hamilton", "Building complex ETL pipelines...", "high-pass", 85))
        conn.commit()
    
    yield db

def test_job_evaluation_logic(test_db):
    # Mock the GenAI client BEFORE instantiating
    with patch('src.llm_client.genai.Client') as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_response = MagicMock()
        mock_response.text = '{"technical_depth": "Deep focus on ETL", "architectural_opportunities": ["Optimize pipelines"], "red_flags": [], "remote_status": "Likely"}'
        mock_response.usage_metadata.total_token_count = 100 # Real integer
        mock_client.models.generate_content.return_value = mock_response

        evaluator = JobEvaluator(test_db)
        
        # Run evaluation
        evaluator.evaluate_all_new()

        # Check database update
        conn = sqlite3.connect(test_db.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT analysis_json FROM jobs WHERE status = 'high-pass'")
        analysis_json = cursor.fetchone()[0]
        assert analysis_json is not None
        assert "Deep focus on ETL" in analysis_json
        assert "Optimize pipelines" in analysis_json
        conn.close()

def test_generate_digest(test_db):
    evaluator = JobEvaluator(test_db)
    
    # Mock data has one job, let's give it an analysis_json manually
    conn = sqlite3.connect(test_db.db_path)
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE jobs SET analysis_json = ? WHERE job_title = ?
    ''', ('{"technical_depth": "Test", "architectural_opportunities": ["Opp1"], "remote_status": "Verified"}', "Senior Data Architect"))
    conn.commit()
    conn.close()
    
    digest_path = evaluator.generate_digest("test_digests")
    assert digest_path is not None
    assert os.path.exists(digest_path)
    
    with open(digest_path, 'r') as f:
        content = f.read()
        assert "Senior Data Architect" in content
        assert "Hamilton" in content
        assert "Verified" in content
    
    # Clean up
    os.remove(digest_path)
    os.rmdir("test_digests")
