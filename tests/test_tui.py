import sqlite3
import pytest
import os
import asyncio
import glob
from textual.widgets import ListView, Label, Markdown, TextArea
from src.review_tui import ReviewApp, JobDetail, JobItem
from src.database import DatabaseManager

@pytest.fixture
def test_db():
    db_path = "data/test_tui.db"
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except PermissionError:
            pass

    db = DatabaseManager(db_path)
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO jobs (job_title, company, location, url, status, score, rationale)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', ("Edge Case Dev", "Startup X", "Remote", "http://job1.com", "edge-case", 65, "Borderline"))
    cursor.execute('''
        INSERT INTO jobs (job_title, company, location, url, status, score, rationale)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', ("Maybe Analyst", "Corp Y", "Hamilton", "http://job2.com", "edge-case", 45, "Needs review"))
    conn.commit()
    conn.close()
    
    yield db

@pytest.mark.asyncio
async def test_review_app_load(test_db):
    app = ReviewApp(test_db)
    async with app.run_test() as pilot:
        job_list = app.query_one("#job-list", ListView)
        assert len(job_list.children) == 2
        
        first_item = job_list.children[0]
        label = first_item.query_one("#job-label", Label)
        assert "Edge Case Dev" in label.render().plain

@pytest.mark.asyncio
async def test_review_app_promote(test_db):
    app = ReviewApp(test_db)
    async with app.run_test() as pilot:
        await pilot.press("p")
        await pilot.press("ctrl+s")
        
        conn = sqlite3.connect(test_db.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM jobs WHERE job_title = 'Edge Case Dev'")
        status = cursor.fetchone()[0]
        conn.close()
        assert status == "high-pass"

@pytest.mark.asyncio
async def test_review_app_staged_decisions(test_db):
    app = ReviewApp(test_db)
    async with app.run_test() as pilot:
        await pilot.press("p")
        
        conn = sqlite3.connect(test_db.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM jobs WHERE job_title = 'Edge Case Dev'")
        status = cursor.fetchone()[0]
        conn.close()
        assert status == "edge-case"
        
        job_list = app.query_one("#job-list", ListView)
        first_item = job_list.children[0]
        assert isinstance(first_item, JobItem)
        assert first_item.staged_status == 'high-pass'
        assert "⬆️" in first_item.get_label_text()

        await pilot.press("ctrl+s")
        
        conn = sqlite3.connect(test_db.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM jobs WHERE job_title = 'Edge Case Dev'")
        status = cursor.fetchone()[0]
        conn.close()
        assert status == "high-pass"

@pytest.mark.asyncio
async def test_review_app_markdown_rendering(test_db):
    app = ReviewApp(test_db)
    async with app.run_test() as pilot:
        details = app.query_one("#details", JobDetail)
        markdown_widget = details.query_one("#markdown-viewer", Markdown)
        assert markdown_widget is not None

@pytest.mark.asyncio
async def test_review_app_human_notes(test_db):
    app = ReviewApp(test_db)
    async with app.run_test() as pilot:
        details = app.query_one("#details", JobDetail)
        notes_input = details.query_one("#notes-input", TextArea)
        notes_input.value = "Great commute, needs Go knowledge."
        
        await pilot.press("p")
        await pilot.press("ctrl+s")
        
        conn = sqlite3.connect(test_db.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT status, notes FROM jobs WHERE job_title = 'Edge Case Dev'")
        row = cursor.fetchone()
        conn.close()
        
        assert row[0] == "high-pass"
        assert row[1] == "Great commute, needs Go knowledge."

@pytest.mark.asyncio
async def test_review_app_full_mode_toggle(test_db):
    app = ReviewApp(test_db)
    async with app.run_test() as pilot:
        job_list = app.query_one("#job-list", ListView)
        header = app.query_one("#list-header", Label)
        
        conn = sqlite3.connect(test_db.db_path)
        conn.execute("INSERT INTO jobs (job_title, company, status) VALUES (?, ?, ?)", 
                     ("Analyzed Architect", "Old Corp", "analyzed"))
        conn.commit()
        conn.close()
        
        await pilot.press("u") # Refresh
        assert len(job_list.children) == 2 # Only edge-case
        
        await pilot.press("f") # Toggle Full Mode
        assert len(job_list.children) == 3
        assert "Full Mode" in header.render().plain
        
        await pilot.press("f") # Toggle Back
        assert len(job_list.children) == 2

@pytest.mark.asyncio
async def test_review_app_digest_view(test_db):
    # Ensure a digest exists
    os.makedirs("digests", exist_ok=True)
    # Clear existing digests for predictable test
    for f in glob.glob("digests/*.md"):
        try: os.remove(f)
        except: pass
        
    with open("digests/digest_test.md", "w") as f:
        f.write("# Latest Digest\n- Job A\n- Job B")
    
    app = ReviewApp(test_db)
    async with app.run_test() as pilot:
        # Toggle to Digest View
        await pilot.press("d")
        
        # Check if Markdown widget exists and is visible
        digest_viewer = app.query_one("#digest-viewer", Markdown)
        assert digest_viewer is not None
        # We can't easily check internal markdown text without 
        # accessing private members or waiting for render.
        # If it didn't crash, we assume it's showing the file.
        
        # Go back
        await pilot.press("escape")
        assert app.query_one("#job-list", ListView).visible

@pytest.mark.asyncio
async def test_review_app_suggestion_view(test_db):
    # Add a suggestion to DB
    conn = sqlite3.connect(test_db.db_path)
    conn.execute("INSERT INTO search_suggestions (keywords, source_keyword, total_jobs) VALUES (?, ?, ?)",
                 ("python developer", "software engineer", 100))
    conn.commit()
    conn.close()
    
    app = ReviewApp(test_db)
    async with app.run_test() as pilot:
        # Toggle to Suggestions View
        await pilot.press("s")
        
        # Check if list contains the suggestion
        s_list = app.query_one("#suggestion-list", ListView)
        assert len(s_list.children) == 1
        assert "python developer" in s_list.children[0].query_one(Label).render().plain
