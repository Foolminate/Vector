import pytest
from src.database import DatabaseManager
from src.review_tui import ReviewApp
from unittest.mock import MagicMock, AsyncMock

@pytest.fixture
def test_db(tmp_path):
    db_path = tmp_path / "test.db"
    return str(db_path)

@pytest.fixture
def migrations_dir():
    return "migrations"

@pytest.mark.asyncio
async def test_validity_check_integrated(test_db, migrations_dir):
    """Verify validity check via integrated logic call with AsyncMock."""
    db_manager = DatabaseManager(db_path=test_db, migrations_dir=migrations_dir)
    
    with db_manager.get_connection() as conn:
        conn.execute(
            "INSERT INTO jobs (job_title, company, location, url, status, expiration_date) VALUES (?, ?, ?, ?, ?, datetime('now', '-1 day'))",
            ("Valid Job", "Co", "Loc", "http://valid.com/job/1", "high-pass")
        )
        conn.execute(
            "INSERT INTO jobs (job_title, company, location, url, status, expiration_date) VALUES (?, ?, ?, ?, ?, datetime('now', '-1 day'))",
            ("Invalid Active", "Co", "Loc", "http://invalid.com/job/2", "edge-case")
        )
        conn.execute(
            "INSERT INTO jobs (job_title, company, location, url, status, expiration_date) VALUES (?, ?, ?, ?, ?, datetime('now', '-1 day'))",
            ("Invalid Rejected", "Co", "Loc", "http://invalid.com/job/3", "discarded")
        )
        conn.commit()

    app = ReviewApp(db_manager)
    app.refresh_list = MagicMock()
    
    # Use AsyncMock for proper awaiting
    mock_check = AsyncMock()
    def side_effect(*args, **kwargs):
        # args[0] is client, args[1] is url
        url = args[1] if len(args) > 1 else kwargs.get('url', '')
        return 1 if str(url) == "http://valid.com/job/1" else 0
    mock_check.side_effect = side_effect
    
    app._check_url_validity = mock_check

    # We need to call the logic directly
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs")
        jobs = [dict(row) for row in cursor.fetchall()]
    
    await app._run_validity_check_logic(jobs)

    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        
        # Valid Job
        cursor.execute("SELECT is_valid, status FROM jobs WHERE job_title = 'Valid Job'")
        row = cursor.fetchone()
        assert row['is_valid'] == 1
        
        # Invalid Active
        cursor.execute("SELECT is_valid, status FROM jobs WHERE job_title = 'Invalid Active'")
        row = cursor.fetchone()
        assert row['is_valid'] == 0
        assert row['status'] == 'edge-case'
        
        # Invalid Rejected (now archived)
        cursor.execute("SELECT is_valid, status FROM jobs WHERE job_title = 'Invalid Rejected'")
        row = cursor.fetchone()
        assert row['is_valid'] == 0
        assert row['status'] == 'archived'
