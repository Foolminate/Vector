import asyncio
from typing import Any, Optional, Type, List
from abc import ABC, abstractmethod
from pydantic import BaseModel
from .database import JobRepository
from .llm_client import ModelAdapter
from .models import TriageResult, EvaluationResult

class BaseStrategy(ABC):
    """Base class for AI pipeline strategies."""
    @abstractmethod
    async def run(self, job_id: str, repo: JobRepository, adapter: ModelAdapter):
        pass

class PipelineObserver(ABC):
    """Interface for pipeline event observers."""
    @abstractmethod
    def on_job_start(self, job_id: str): pass
    @abstractmethod
    def on_job_complete(self, job_id: str): pass
    @abstractmethod
    def on_job_error(self, job_id: str, error: str): pass
    @abstractmethod
    def on_queue_empty(self): pass

class AgentPipeline:
    """
    Async pipeline for processing jobs through various AI strategies.
    Handles queuing, concurrency, and error isolation.
    """
    def __init__(self, repo: JobRepository, adapter: ModelAdapter, concurrency: int = 3):
        self.repo = repo
        self.adapter = adapter
        self.queue = asyncio.Queue()
        self.semaphore = asyncio.Semaphore(concurrency)
        self.observers: List[PipelineObserver] = []

    def subscribe(self, observer: PipelineObserver):
        self.observers.append(observer)

    def push(self, job_id: str):
        """Add a job ID to the processing queue."""
        self.queue.put_nowait(job_id)

    async def process_queue(self, strategy: BaseStrategy):
        """
        Background worker that processes the queue using the given strategy.
        Runs until cancelled.
        """
        while True:
            job_id = await self.queue.get()
            try:
                for obs in self.observers: obs.on_job_start(job_id)
                
                async with self.semaphore:
                    # Run the strategy in a thread if it's not async-native
                    # (Though here we assume the strategy.run is async)
                    await strategy.run(job_id, self.repo, self.adapter)
                
                for obs in self.observers: obs.on_job_complete(job_id)
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Pipeline Error on job {job_id}: {e}")
                for obs in self.observers: obs.on_job_error(job_id, str(e))
            finally:
                self.queue.task_done()
                if self.queue.empty():
                    for obs in self.observers: obs.on_queue_empty()

# --- Specific Strategies ---

class TriageStrategy(BaseStrategy):
    """
    Implements the Triage (Sorter) stage of the pipeline.
    """
    def __init__(self, prompt_template: Optional[str] = None, decision_by: str = 'robot'):
        self.decision_by = decision_by
        self.prompt_template = prompt_template or """
        Analyze the following job posting and provide a triage score (0-100) 
        and a brief reason. 
        Focus on: technical relevance, location fit, and role seniority.
        
        Job Title: {title}
        Company: {company}
        Location: {location}
        Description: {description}
        """

    async def run(self, job_id: str, repo: JobRepository, adapter: ModelAdapter):
        # 1. Fetch job data
        with repo.get_connection() as conn:
            row = conn.execute('''
                SELECT job_title, company, location, raw_text 
                FROM jobs WHERE seek_job_id = ? OR id = ?
            ''', (job_id, job_id)).fetchone()
            if not row:
                return
            job = dict(row)

        # 2. Prepare prompt
        prompt = self.prompt_template.format(
            title=job['job_title'],
            company=job['company'],
            location=job['location'],
            description=job['raw_text'][:5000] # Limit context size
        )

        # 3. Call LLM (synchronous call wrapped in to_thread)
        result = await asyncio.to_thread(
            adapter.generate_json,
            prompt=prompt,
            response_model=TriageResult,
            task="triage"
        )

        # 4. Update repository (Deep Module handles state transition)
        repo.mark_triage_complete(
            job_id=job_id,
            score=result.score,
            analysis={"reason": result.reason},
            decision_by=self.decision_by
        )

class EvaluationStrategy(BaseStrategy):
    """
    Implements the Deep Synthesis (Evaluator) stage of the pipeline.
    """
    def __init__(self, prompt_template: Optional[str] = None, decision_by: str = 'robot'):
        self.decision_by = decision_by
        self.prompt_template = prompt_template or """
        Perform a deep qualitative analysis on this job posting.
        Determine if this is a high-value opportunity.
        
        Job Title: {title}
        Company: {company}
        Location: {location}
        Description: {description}
        
        Output a suitability score (0-100), a list of pros, a list of cons, 
        and a final verdict ('shortlisted', 'edge-case', 'discarded').
        """

    async def run(self, job_id: str, repo: JobRepository, adapter: ModelAdapter):
        # 1. Fetch job data
        with repo.get_connection() as conn:
            row = conn.execute('''
                SELECT job_title, company, location, raw_text 
                FROM jobs WHERE seek_job_id = ? OR id = ?
            ''', (job_id, job_id)).fetchone()
            if not row:
                return
            job = dict(row)

        # 2. Prepare prompt
        prompt = self.prompt_template.format(
            title=job['job_title'],
            company=job['company'],
            location=job['location'],
            description=job['raw_text'][:8000] # Deeper context for Agent 2
        )

        # 3. Call LLM
        result = await asyncio.to_thread(
            adapter.generate_json,
            prompt=prompt,
            response_model=EvaluationResult,
            task="evaluation"
        )

        # 4. Update repository
        repo.mark_evaluation_complete(
            job_id=job_id,
            score=result.suitability_score,
            analysis={
                "pros": result.pros,
                "cons": result.cons
            },
            verdict=result.verdict,
            decision_by=self.decision_by
        )
