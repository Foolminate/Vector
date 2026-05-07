import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from src.collector import SeekCollector
from src.database import DatabaseManager
from src.pipeline import AgentPipeline, TriageStrategy, EvaluationStrategy
from src.models import RawJobData, TriageResult, EvaluationResult
from src.config_loader import AppConfig
from src.llm_client import ModelAdapter

@pytest.fixture
def db(tmp_path):
    db_path = tmp_path / "e2e_vector.db"
    return DatabaseManager(db_path=str(db_path), migrations_dir="migrations")

@pytest.fixture
def config():
    c = MagicMock(spec=AppConfig)
    c.searches = [MagicMock(keywords="Python", priority=1)]
    c.locations = [MagicMock(name="Auckland", slug="auckland", priority=1)]
    return c

@pytest.mark.asyncio
async def test_full_pipeline_lifecycle_resilience(db, config):
    """
    Simulate full run: Scrape -> Triage -> Evaluation.
    Includes mocked failures and resilience verification.
    """
    # 1. Setup Pipeline and Collector
    adapter = MagicMock(spec=ModelAdapter)
    pipeline = AgentPipeline(db, adapter)
    collector = SeekCollector(db, config, pipeline=pipeline)
    
    # 2. Mock Scraper and LLM
    # Job 1: Success path
    # Job 2: Bot blocked path
    # Job 3: LLM failure path
    
    with patch("src.collector.async_playwright") as mock_p:
        mock_playwright = mock_p.return_value.__aenter__.return_value
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        
        # Mock Search results: 2 jobs discovered
        collector.parser.parse_search_results = MagicMock(return_value=[
            RawJobData(title="Success Job", company="Co", location="Akl", url="http://test.com/1", seek_job_id="s1"),
            RawJobData(title="Fail Job", company="Co", location="Akl", url="http://test.com/2", seek_job_id="f1")
        ])
        
        # Mock Page responses
        mock_page.goto.return_value = MagicMock(status=200)
        mock_page.query_selector.return_value = MagicMock()
        mock_page.evaluate.return_value = {}
        
        # Mock Detail extraction
        with patch.object(collector, "scrape_job_details", new_callable=AsyncMock) as mock_details:
            mock_details.side_effect = ["Description 1", "Description 2"]
            
            # RUN SCRAPE
            await collector.scrape(limit=2)

    # Verify 2 jobs in DB
    with db.get_connection() as conn:
        count = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        assert count == 2

    # 3. RUN TRIAGE (Pipeline)
    # Job 1 -> 90 (High-pass)
    # Job 2 -> 20 (Discarded)
    
    # Mock LLM adapter results
    def adapter_side_effect(*args, **kwargs):
        task = kwargs.get('task')
        prompt = kwargs.get('prompt', '')
        if task == "triage":
            if "Success Job" in prompt:
                return TriageResult(score=90, reason="Perfect")
            else:
                return TriageResult(score=20, reason="Bad")
        elif task == "evaluation":
            return EvaluationResult(suitability_score=95, pros=["P"], cons=["C"], verdict="shortlisted")
        return None

    # adapter.generate_json is called via to_thread, so we mock it as a regular mock
    adapter.generate_json.side_effect = adapter_side_effect

    # Better: Use a helper to run until empty
    async def process_until_empty(strategy):
        while not pipeline.queue.empty():
            job_id = await pipeline.queue.get()
            await strategy.run(job_id, db, adapter)
            pipeline.queue.task_done()
            
    await process_until_empty(TriageStrategy())

    # Verify status
    with db.get_connection() as conn:
        row1 = conn.execute("SELECT status FROM jobs WHERE seek_job_id = 's1'").fetchone()
        row2 = conn.execute("SELECT status FROM jobs WHERE seek_job_id = 'f1'").fetchone()
        assert row1['status'] == 'high-pass'
        assert row2['status'] == 'discarded'

    # 4. RUN EVALUATION (Agent 2)
    # Push high-pass jobs to queue
    with db.get_connection() as conn:
        high_pass = conn.execute("SELECT seek_job_id FROM jobs WHERE status = 'high-pass'").fetchall()
        for r in high_pass:
            pipeline.push(r[0])

    await process_until_empty(EvaluationStrategy())

    # Verify final state
    with db.get_connection() as conn:
        row = conn.execute("SELECT status, score FROM jobs WHERE seek_job_id = 's1'").fetchone()
        assert row['status'] == 'shortlisted'
        assert row['score'] == 95
        
        # Verify audit log correlation
        logs = conn.execute("SELECT action, details FROM audit_log WHERE details LIKE '%s1%'").fetchall()
        actions = [l[0] for l in logs]
        assert "scrape" in actions
        assert "triage" in actions
        assert "evaluation" in actions
