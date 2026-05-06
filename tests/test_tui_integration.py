import pytest
import os
import sqlite3
from textual.widgets import TextArea, ListView
from src.review_tui import ReviewApp
from src.database import DatabaseManager

@pytest.fixture
def temp_db(tmp_path):
    db_path = tmp_path / "test_vector.db"
    db = DatabaseManager(db_path=str(db_path))
    
    # Seed with one job
    with db.get_connection() as conn:
        conn.execute('''
            INSERT INTO jobs (job_title, company, location, url, raw_text, status, seek_job_id, score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', ("Test Job", "Test Co", "Test Loc", "http://test.com", "Test text", "new", "seek-123", 50))
        conn.commit()
    
    return db

@pytest.mark.asyncio
async def test_tui_note_persistence(temp_db):
    app = ReviewApp(temp_db)
    async with app.run_test() as pilot:
        # Check if job is loaded
        job_list = app.query_one("#job-list", ListView)
        assert len(job_list.children) == 1
        
        # Enter a note
        note_area = app.query_one("#notes-input", TextArea)
        note_area.value = "This is a test human note."
        
        # Press 'ctrl+s' to save (matches Binding("ctrl+s", "save", "Confirm & Save"))
        await pilot.press("ctrl+s")
        
        # Verify in DB
        with temp_db.get_connection() as conn:
            cursor = conn.execute("SELECT notes, last_decision_by FROM jobs WHERE seek_job_id = 'seek-123'")
            row = cursor.fetchone()
            assert row["notes"] == "This is a test human note."
            assert row["last_decision_by"] == "human"

@pytest.mark.asyncio
async def test_tui_status_transition(temp_db):
    app = ReviewApp(temp_db)
    async with app.run_test() as pilot:
        # Promote the job (Press 'p')
        await pilot.press("p")
        # Save (Press 'ctrl+s')
        await pilot.press("ctrl+s")
        
        # Verify in DB
        with temp_db.get_connection() as conn:
            cursor = conn.execute("SELECT status, last_decision_by FROM jobs WHERE seek_job_id = 'seek-123'")
            row = cursor.fetchone()
            assert row["status"] == "high-pass"
            assert row["last_decision_by"] == "human"

@pytest.mark.asyncio
async def test_tui_new_job_visual(temp_db):
    app = ReviewApp(temp_db)
    async with app.run_test() as pilot:
        job_item = app.query_one("#job-list", ListView).children[0]
        label_text = job_item.get_label_text()
        assert "✨" in label_text
        assert "New" in label_text or "Test Job" in label_text
