from pydantic import BaseModel, Field, HttpUrl
from typing import List, Optional
from datetime import datetime

class RawJobData(BaseModel):
    """Schema for data extracted by the scraper/parser."""
    title: str
    company: Optional[str] = None
    location: Optional[str] = None
    url: HttpUrl
    seek_job_id: str
    raw_text: Optional[str] = None
    expiration_date: Optional[datetime] = None

class TriageResult(BaseModel):
    """Schema for Agent 1 (Sorter) output."""
    score: int = Field(..., ge=0, le=100)
    reason: str

class EvaluationResult(BaseModel):
    """Schema for Agent 2 (Evaluator) output."""
    suitability_score: int = Field(..., ge=0, le=100)
    pros: List[str]
    cons: List[str]
    verdict: str = Field(..., pattern="^(shortlisted|edge-case|discarded)$")
