import pytest
from src.database import DatabaseManager
from src.review_tui import ReviewApp
from unittest.mock import MagicMock, patch, AsyncMock

@pytest.fixture
def test_db(tmp_path):
    db_path = tmp_path / "test.db"
    return str(db_path)

@pytest.fixture
def migrations_dir():
    return "migrations"

@pytest.mark.asyncio
async def test_force_digest_updates_attribution(test_db, migrations_dir):
    """Verify that 'action_force_digest' sets last_decision_by to 'human'."""
    db_manager = DatabaseManager(db_path=test_db, migrations_dir=migrations_dir)
    
    with db_manager.get_connection() as conn:
        conn.execute(
            "INSERT INTO jobs (job_title, company, location, url, raw_text, status, last_decision_by) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("Force Job", "Co", "Loc", "http://force.com", "Text", "high-pass", "robot")
        )
        conn.commit()
        
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE job_title = 'Force Job'")
        job_data = list(cursor.fetchone())

    app = ReviewApp(db_manager)
    app.current_job = job_data
    app.refresh_list = MagicMock()
    app.notify = MagicMock()

    # We patch asyncio.to_thread to run the functions synchronously for testing
    async def mock_to_thread(func, *args, **kwargs):
        if func.__name__ == 'evaluate_job':
            return {"verdict": "shortlisted", "technical_depth": "High", "rationale": "Mocked"}
        if func.__name__ == 'save_evaluation':
            # Run the actual save method, but we know it sets 'robot' initially
            from src.evaluator import JobEvaluator
            evaluator = JobEvaluator(db_manager)
            evaluator.save_evaluation(*args)
            return None
        return func(*args, **kwargs)

    with patch("asyncio.to_thread", side_effect=mock_to_thread):
        # Call the logic method directly, bypassing @work
        await app._run_single_evaluation_logic(job_data)

    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT last_decision_by, status FROM jobs WHERE job_title = 'Force Job'")
        row = cursor.fetchone()
        
        assert row['status'] == 'shortlisted'
        assert row['last_decision_by'] == 'human'
