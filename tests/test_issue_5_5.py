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
        job_data = dict(cursor.fetchone())

    app = ReviewApp(db_manager)
    app.current_job = job_data
    app.refresh_list = MagicMock()
    app.notify = MagicMock()

    # We need to mock the UI components that run_single_evaluation queries
    app.query_one = MagicMock()
    mock_pb = MagicMock()
    app.query_one.return_value = mock_pb

    # Patch the pipeline to run the strategy directly
    with patch.object(app.pipeline, "process_queue", new_callable=AsyncMock) as mock_process:
        await app._run_single_evaluation_logic(job_data)
        # Verify the strategy was called with decision_by='human'
        strategy = mock_process.call_args[0][0]
        assert strategy.decision_by == 'human'

    # Manually run a repository update to simulate the strategy finishing
    db_manager.mark_evaluation_complete(job_data['id'], {}, 'shortlisted', decision_by='human')

    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT last_decision_by, status FROM jobs WHERE job_title = 'Force Job'")
        row = cursor.fetchone()
        
        assert row['status'] == 'shortlisted'
        assert row['last_decision_by'] == 'human'
