import sqlite3
import pytest
from textual.widgets import ListView, Label
from src.review_tui import ReviewApp
from src.database import DatabaseManager
import os
import asyncio

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
        label = first_item.query_one(Label)
        assert "Edge Case Dev" in str(label.render())

@pytest.mark.asyncio
async def test_review_app_promote(test_db):
    app = ReviewApp(test_db)
    async with app.run_test() as pilot:
        job_list = app.query_one("#job-list", ListView)
        
        # Auto-selected on refresh_list() call in on_mount()
        await pilot.press("p")
        
        conn = sqlite3.connect(test_db.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM jobs WHERE job_title = 'Edge Case Dev'")
        status = cursor.fetchone()[0]
        conn.close()
        assert status == "high-pass"
        assert len(job_list.children) == 1

@pytest.mark.asyncio
async def test_review_app_reject(test_db):
    app = ReviewApp(test_db)
    async with app.run_test() as pilot:
        job_list = app.query_one("#job-list", ListView)
        
        await pilot.press("r")
        
        conn = sqlite3.connect(test_db.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM jobs WHERE job_title = 'Edge Case Dev'")
        status = cursor.fetchone()[0]
        conn.close()
        assert status == "rejected"
        assert len(job_list.children) == 1
