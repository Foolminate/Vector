import pytest
from src.parser import SeekParser

def test_parse_search_results_redux():
    """Test extraction from Seek Redux data."""
    parser = SeekParser()
    mock_redux = {
        "results": {
            "jobIds": ["123"],
            "jobs": [
                {
                    "id": "123",
                    "title": "Software Engineer",
                    "advertiser": {"description": "Tech Co"},
                    "location": "Auckland",
                    "listingDate": "2024-05-01T00:00:00Z"
                }
            ]
        }
    }
    
    jobs = parser.parse_search_results(redux_data=mock_redux, html="")
    assert len(jobs) == 1
    assert jobs[0]['title'] == "Software Engineer"
    assert jobs[0]['company'] == "Tech Co"
    assert jobs[0]['seek_job_id'] == "123"
    assert "published_at" in jobs[0]

def test_parse_search_results_dom_fallback():
    """Test extraction from DOM when Redux is missing."""
    parser = SeekParser()
    mock_html = """
    <html>
        <body>
            <div data-automation="jobCard" data-job-id="456">
                <a data-automation="jobTitle">Data Scientist</a>
                <span data-automation="jobCompany">Data Corp</span>
                <span data-automation="jobLocation">Wellington</span>
            </div>
        </body>
    </html>
    """
    
    jobs = parser.parse_search_results(redux_data={}, html=mock_html)
    assert len(jobs) == 1
    assert jobs[0]['title'] == "Data Scientist"
    assert jobs[0]['company'] == "Data Corp"
    assert jobs[0]['seek_job_id'] == "456"

def test_parse_job_details():
    """Test extraction of job description."""
    parser = SeekParser()
    mock_html = """
    <html>
        <body>
            <div data-automation="jobAdDetails">
                This is a very cool job description.
            </div>
        </body>
    </html>
    """
    description = parser.parse_job_details(mock_html)
    assert "very cool job description" in description
