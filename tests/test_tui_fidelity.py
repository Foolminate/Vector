import pytest
import asyncio
from unittest.mock import MagicMock
from src.pipeline import AgentPipeline, PipelineObserver, BaseStrategy

class MockStrategy(BaseStrategy):
    async def run(self, job_id, repo, adapter):
        await asyncio.sleep(0.1)

@pytest.mark.asyncio
async def test_pipeline_observer_notifications():
    repo = MagicMock()
    adapter = MagicMock()
    pipeline = AgentPipeline(repo, adapter)
    observer = MagicMock(spec=PipelineObserver)
    pipeline.subscribe(observer)
    
    pipeline.push("job-1")
    
    # Process for a bit
    task = asyncio.create_task(pipeline.process_queue(MockStrategy()))
    await asyncio.sleep(0.2)
    task.cancel()
    
    # Verify observer was called
    observer.on_job_start.assert_called_with("job-1")
    observer.on_job_complete.assert_called_with("job-1")
    observer.on_queue_empty.assert_called()

def test_job_item_processing_status_visual():
    from src.review_tui import JobItem
    
    # job_data dictionary as expected by refactored TUI
    job_data = {
        "id": 1,
        "job_title": "Test Job",
        "company": "Test Co",
        "score": 50,
        "status": "new",
        "is_valid": 1,
        "last_decision_by": "robot",
        "processing_status": "analyzing"
    }
    
    item = JobItem(job_data)
    label = item.get_label_text()
    assert "🔄" in label
