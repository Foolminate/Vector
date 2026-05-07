import pytest
import os
from unittest.mock import MagicMock
from src.sorter import TriageSorter
from src.database import DatabaseManager

@pytest.fixture
def mock_db():
    return MagicMock(spec=DatabaseManager)

def test_sorter_init_missing_doctrine(mock_db):
    """Verify that TriageSorter uses a fallback if DOCTRINE.md is missing."""
    sorter = TriageSorter(mock_db, doctrine_path="non_existent.md")
    assert "Standard Triage Doctrine" in sorter.doctrine
    assert "technical relevance" in sorter.doctrine.lower()

def test_sorter_load_doctrine_fallback(mock_db, tmp_path):
    """Confirm it loads correctly when present."""
    doctrine_file = tmp_path / "DOCTRINE.md"
    doctrine_file.write_text("Test Doctrine")
    
    sorter = TriageSorter(mock_db, doctrine_path=str(doctrine_file))
    assert sorter.doctrine == "Test Doctrine"

def test_triage_job_scoring_branches(mock_db):
    """Verify that triage_job returns the LLM result correctly."""
    sorter = TriageSorter(mock_db)
    sorter.llm = MagicMock()
    
    # Mock LLM response
    expected_result = {"score": 85, "rationale": "Matches doctrine"}
    sorter.llm.generate_json.return_value = expected_result
    
    result = sorter.triage_job(1, "Title", "Company", "Loc", "Desc")
    assert result == expected_result
    sorter.llm.generate_json.assert_called_once()

def test_update_job_status_standardization(mock_db):
    """Verify that update_job_status calls mark_triage_complete with standardized logic."""
    sorter = TriageSorter(mock_db)
    
    result = {"score": 90, "rationale": "High relevance"}
    sorter.update_job_status(1, result)
    
    # mark_triage_complete should be called with score and analysis dict
    mock_db.mark_triage_complete.assert_called_with(1, 90, {"rationale": "High relevance"})
    mock_db.log_action.assert_called_with("triage", "Job 1 scored 90")

def test_update_job_status_invalid_result(mock_db):
    """Verify handling of non-dict results from LLM."""
    sorter = TriageSorter(mock_db)
    
    sorter.update_job_status(1, "not a dict")
    mock_db.mark_triage_complete.assert_not_called()

def test_triage_job_exception_handling(mock_db):
    """Verify that triage_job handles LLM exceptions gracefully."""
    sorter = TriageSorter(mock_db)
    sorter.llm = MagicMock()
    sorter.llm.generate_json.side_effect = Exception("LLM Down")
    
    result = sorter.triage_job(1, "Title", "Company", "Loc", "Desc")
    assert result is None

def test_triage_all_new(mock_db):
    """Verify that triage_all_new processes jobs correctly."""
    sorter = TriageSorter(mock_db)
    
    # Mock database connection and cursor
    mock_conn = MagicMock()
    mock_db.get_connection.return_value.__enter__.return_value = mock_conn
    
    mock_conn.cursor.return_value.fetchall.return_value = [
        (1, "Title 1", "Company 1", "Loc 1", "Desc 1"),
        (2, "Title 2", "Company 2", "Loc 2", "Desc 2")
    ]
    
    # Mock triage_job to avoid actual LLM calls
    sorter.triage_job = MagicMock(return_value={"score": 50, "rationale": "ok"})
    
    sorter.triage_all_new()
    
    assert sorter.triage_job.call_count == 2
    assert mock_db.mark_triage_complete.call_count == 2
    assert mock_db.log_action.call_count == 2

def test_triage_all_new_empty(mock_db):
    """Verify that triage_all_new handles empty list correctly."""
    sorter = TriageSorter(mock_db)
    
    mock_conn = MagicMock()
    mock_db.get_connection.return_value.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.fetchall.return_value = []
    
    sorter.triage_all_new()
    # Should not crash and should return early
    mock_db.mark_triage_complete.assert_not_called()
