import pytest
from src.review_tui import JobItem
from textual.widgets import Label

def create_mock_job(id=1, title="DevOps Engineer", company="Tech Corp", score=90, status="new", is_valid=1, last_decision_by="robot"):
    # Mocking the 18-column structure from the database
    # 0:id, 1:title, 2:company, 3:location, 4:url, 5:text, 6:status, 7:score, 8:rationale, 9:analysis, 10:created, 11:seek_id, 12:notes, 13:last_checked, 14:is_valid, 15:last_decision_by, 16:expiration
    return [
        id, title, company, "Hamilton", "http://test.com", "Text", status, score, "Rationale", None, "2026-05-05", "seek-123", "", None, is_valid, last_decision_by, "2026-06-05"
    ]

def test_job_item_emoji_mapping():
    """Verify that JobItem displays the correct emojis for various states."""
    # New job by robot
    job = create_mock_job(status="new", last_decision_by="robot")
    item = JobItem(job)
    assert "✨🤖" in item.get_label_text()
    
    # Shortlisted by robot
    job = create_mock_job(status="shortlisted", last_decision_by="robot")
    item = JobItem(job)
    assert "✅🤖" in item.get_label_text()

    # Edge-case by robot
    job = create_mock_job(status="edge-case", last_decision_by="robot")
    item = JobItem(job)
    assert "❓🤖" in item.get_label_text()

    # Expired job (invalid)
    job = create_mock_job(status="high-pass", is_valid=0)
    item = JobItem(job)
    assert "⏰" in item.get_label_text()

    # Staged Promote
    job = create_mock_job(status="new")
    item = JobItem(job, staged_status="high-pass")
    assert "⬆️👤" in item.get_label_text()

    # Staged Delete
    job = create_mock_job(status="new")
    item = JobItem(job, staged_status="deleted")
    assert "🗑️👤" in item.get_label_text()

def test_job_item_visual_classes():
    """Verify that JobItem applies the correct CSS classes for visual grouping."""
    # Expired
    job = create_mock_job(is_valid=0)
    item = JobItem(job)
    item.get_label_text() # Trigger class assignment
    assert "expired" in item.classes

    # Urgent (Edge-case)
    job = create_mock_job(status="edge-case")
    item = JobItem(job)
    item.get_label_text()
    assert "urgent" in item.classes

    # Staged Promote
    job = create_mock_job(status="new")
    item = JobItem(job, staged_status="high-pass")
    item.get_label_text()
    assert "staged-promote" in item.classes

    # Bright Shortlist
    job = create_mock_job(status="shortlisted", last_decision_by="robot")
    item = JobItem(job)
    item.get_label_text()
    assert "bright-shortlist" in item.classes
