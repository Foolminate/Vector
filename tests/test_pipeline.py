import pytest
import asyncio
from unittest.mock import MagicMock
from src.pipeline import AgentPipeline, BaseStrategy
from src.database import JobRepository

class MockStrategy(BaseStrategy):
    async def run(self, job_id, repo, adapter):
        # Simulate work
        repo.mark_triage_complete(job_id, score=100, analysis={"msg": "Done"})

@pytest.fixture
def test_db(tmp_path):
    db_path = tmp_path / "test_pipeline.db"
    return str(db_path)

@pytest.mark.asyncio
async def test_pipeline_processing(test_db):
    repo = JobRepository(db_path=test_db)
    # Upsert a job
    repo.upsert_job({"id": "p1", "title": "Pipeline Job", "url": "p1url"})
    
    pipeline = AgentPipeline(repo=repo, adapter=MagicMock())
    pipeline.push("p1")
    
    # Run the worker in background
    worker_task = asyncio.create_task(pipeline.process_queue(strategy=MockStrategy()))
    
    # Wait for the queue to be empty (with timeout)
    try:
        await asyncio.wait_for(pipeline.queue.join(), timeout=2.0)
    finally:
        worker_task.cancel()
    
    # Check DB
    with repo.get_connection() as conn:
        row = conn.execute("SELECT status FROM jobs WHERE seek_job_id='p1'").fetchone()
        assert row['status'] == 'high-pass'

@pytest.mark.asyncio
async def test_pipeline_error_isolation(test_db):
    repo = JobRepository(db_path=test_db)
    repo.upsert_job({"id": "fail", "title": "Fail Job", "url": "failurl"})
    repo.upsert_job({"id": "success", "title": "Success Job", "url": "successurl"})
    
    class FailingStrategy(BaseStrategy):
        async def run(self, job_id, repo, adapter):
            if job_id == "fail":
                raise Exception("Boom")
            repo.mark_triage_complete(job_id, score=100, analysis={"msg": "Done"})

    pipeline = AgentPipeline(repo=repo, adapter=MagicMock())
    pipeline.push("fail")
    pipeline.push("success")
    
    worker_task = asyncio.create_task(pipeline.process_queue(strategy=FailingStrategy()))
    
    try:
        await asyncio.wait_for(pipeline.queue.join(), timeout=2.0)
    finally:
        worker_task.cancel()
        
    # Success job should be completed despite fail job
    with repo.get_connection() as conn:
        row = conn.execute("SELECT status FROM jobs WHERE seek_job_id='success'").fetchone()
        assert row['status'] == 'high-pass'
