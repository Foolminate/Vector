import pytest
from pydantic import ValidationError
from src.models import RawJobData, TriageResult, EvaluationResult

def test_raw_job_data_validation():
    # Valid data
    data = {
        "title": "Software Engineer",
        "company": "Tech Corp",
        "location": "Auckland",
        "url": "https://nz.seek.com/job/123",
        "seek_job_id": "123"
    }
    job = RawJobData(**data)
    assert job.title == "Software Engineer"
    
    # Invalid URL
    data["url"] = "not-a-url"
    with pytest.raises(ValidationError):
        RawJobData(**data)

def test_triage_result_validation():
    # Valid
    res = TriageResult(score=85, reason="Great match")
    assert res.score == 85
    
    # Invalid score (too high)
    with pytest.raises(ValidationError):
        TriageResult(score=101, reason="Too high")
        
    # Invalid score (too low)
    with pytest.raises(ValidationError):
        TriageResult(score=-1, reason="Too low")
    
    # Missing fields
    with pytest.raises(ValidationError):
        TriageResult(score=50) # Missing reason

def test_evaluation_result_validation():
    # Valid
    res = EvaluationResult(
        suitability_score=90,
        pros=["Expertise", "Location"],
        cons=["Salary hidden"],
        verdict="shortlisted"
    )
    assert res.verdict == "shortlisted"
    
    # Invalid verdict
    with pytest.raises(ValidationError):
        EvaluationResult(
            suitability_score=90,
            pros=[],
            cons=[],
            verdict="invalid-verdict"
        )
    
    # Invalid score (too high)
    with pytest.raises(ValidationError):
        EvaluationResult(
            suitability_score=150,
            pros=[],
            cons=[],
            verdict="shortlisted"
        )
