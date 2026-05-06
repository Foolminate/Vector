import pytest
import asyncio
from unittest.mock import MagicMock
from src.pipeline import EvaluationStrategy, EvaluationResult
from src.database import JobRepository

@pytest.fixture
def test_db(tmp_path):
    db_path = tmp_path / "test_eval.db"
    return str(db_path)

@pytest.mark.asyncio
async def test_evaluation_strategy_preserves_discarded(test_db):
    """Test that EvaluationStrategy saves analysis even for 'discarded' verdict."""
    repo = JobRepository(db_path=test_db)
    job_id = "eval-1"
    repo.upsert_job({
        "id": job_id,
        "title": "Bad Job",
        "company": "Bad Co",
        "location": "Nowhere",
        "url": "url",
        "raw_html": "..."
    })
    
    mock_adapter = MagicMock()
    mock_result = EvaluationResult(
        suitability_score=10,
        pros=["None"],
        cons=["Everything"],
        verdict="discarded"
    )
    mock_adapter.generate_json.return_value = mock_result
    
    strategy = EvaluationStrategy()
    await strategy.run(job_id, repo, mock_adapter)
    
    # Check DB: status should be 'discarded' AND analysis_json should be present
    with repo.get_connection() as conn:
        row = conn.execute("SELECT status, analysis_json FROM jobs WHERE seek_job_id=?", (job_id,)).fetchone()
        assert row['status'] == 'discarded'
        assert row['analysis_json'] is not None
        assert "Everything" in row['analysis_json']

@pytest.mark.asyncio
async def test_reset_for_evaluation(test_db):
    """Test that reset_for_evaluation sets status back to 'high-pass'."""
    repo = JobRepository(db_path=test_db)
    job_id = "reset-1"
    repo.upsert_job({"id": job_id, "title": "Job", "url": "url"})
    
    # Set to discarded first
    repo.mark_evaluation_complete(job_id, score=10, analysis={}, verdict="discarded")
    
    # Reset
    repo.reset_for_evaluation(job_id)
    
    with repo.get_connection() as conn:
        row = conn.execute("SELECT status FROM jobs WHERE seek_job_id=?", (job_id,)).fetchone()
        assert row['status'] == 'high-pass'
