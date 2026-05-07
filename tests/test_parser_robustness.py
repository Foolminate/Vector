import pytest
from src.parser import SeekParser
from src.models import RawJobData

def test_parse_search_results_returns_raw_job_data():
    parser = SeekParser()
    redux_data = {
        "results": {
            "jobs": [
                {
                    "id": "12345",
                    "title": "Software Engineer",
                    "advertiser": {"description": "Tech Corp"},
                    "location": "Auckland",
                    "listingDate": "2024-05-01T00:00:00Z"
                }
            ]
        }
    }
    
    results = parser.parse_search_results(redux_data, "")
    assert len(results) == 1
    assert isinstance(results[0], RawJobData)
    assert results[0].seek_job_id == "12345"
    assert results[0].title == "Software Engineer"
    assert results[0].company == "Tech Corp"
    assert results[0].location == "Auckland"
    assert str(results[0].url) == "https://nz.seek.com/job/12345"

def test_parse_from_dom_returns_raw_job_data():
    parser = SeekParser()
    html = """
    <div data-automation="jobCard" data-job-id="67890">
        <a data-automation="jobTitle" href="/job/67890">Senior Developer</a>
        <a data-automation="jobCompany">Soft Systems</a>
        <a data-automation="jobLocation">Wellington</a>
    </div>
    """
    results = parser.parse_search_results({}, html)
    assert len(results) == 1
    assert isinstance(results[0], RawJobData)
    assert results[0].seek_job_id == "67890"
    assert results[0].title == "Senior Developer"
    assert results[0].company == "Soft Systems"
    assert results[0].location == "Wellington"
