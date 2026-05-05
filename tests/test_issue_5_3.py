import pytest
from src.database import DatabaseManager
from src.review_tui import ReviewApp, JobItem
from textual.widgets import ListView

@pytest.fixture
def test_db(tmp_path):
    db_path = tmp_path / "test.db"
    return str(db_path)

@pytest.fixture
def migrations_dir():
    return "migrations"

@pytest.mark.asyncio
async def test_mark_delete_and_clear_stage(test_db, migrations_dir):
    """Verify that 'x' marks for deletion and 'backspace' clears the staged change."""
    db_manager = DatabaseManager(db_path=test_db, migrations_dir=migrations_dir)
    with db_manager.get_connection() as conn:
        conn.execute(
            "INSERT INTO jobs (job_title, company, location, url, raw_text, status) VALUES (?, ?, ?, ?, ?, ?)",
            ("Delete Job", "Co", "Loc", "http://delete.com", "Text", "new")
        )
        conn.commit()
        job_id = conn.execute("SELECT id FROM jobs").fetchone()[0]

    app = ReviewApp(db_manager)
    async with app.run_test() as pilot:
        # Wait for items to load
        await pilot.pause()
        
        # Verify initial state
        job_list = app.query_one("#job-list", ListView)
        assert len(job_list.children) > 0
        
        # Mark for deletion
        await pilot.press("x")
        assert app.staged_changes[job_id] == 'deleted'
        
        # Undo (clear stage)
        await pilot.press("backspace")
        assert job_id not in app.staged_changes

@pytest.mark.asyncio
async def test_action_save_hard_deletion(test_db, migrations_dir):
    """Verify that 'action_save' performs hard deletion for jobs marked as 'deleted'."""
    db_manager = DatabaseManager(db_path=test_db, migrations_dir=migrations_dir)
    with db_manager.get_connection() as conn:
        conn.execute(
            "INSERT INTO jobs (job_title, company, location, url, raw_text, status) VALUES (?, ?, ?, ?, ?, ?)",
            ("Hard Delete Job", "Co", "Loc", "http://hard-delete.com", "Text", "new")
        )
        conn.commit()
        job_id = conn.execute("SELECT id FROM jobs").fetchone()[0]

    app = ReviewApp(db_manager)
    async with app.run_test() as pilot:
        await pilot.pause()
        
        # Mark for deletion
        await pilot.press("x")
        
        # Confirm & Save
        await pilot.press("ctrl+s")
        await pilot.pause()
        
        # Verify hard deletion in DB
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
            assert cursor.fetchone() is None
