import pytest
from src.collector import SeekCollector
from src.database import DatabaseManager

@pytest.fixture
def collector(tmp_path):
    db_path = str(tmp_path / "test_collector.db")
    db = DatabaseManager(db_path, migrations_dir="migrations")
    return SeekCollector(db, {})

def test_is_valid_nz_location(collector):
    # Valid NZ locations
    assert collector._is_valid_nz_location("Hamilton, Waikato") is True
    assert collector._is_valid_nz_location("Auckland City, Auckland") is True
    assert collector._is_valid_nz_location("Wellington") is True
    assert collector._is_valid_nz_location("Remote") is True
    
    # Invalid AU locations
    assert collector._is_valid_nz_location("Melbourne, VIC") is False
    assert collector._is_valid_nz_location("Sydney, NSW") is False
    assert collector._is_valid_nz_location("Brisbane, QLD") is False
    assert collector._is_valid_nz_location("Perth, WA") is False
    assert collector._is_valid_nz_location("Adelaide, Australia") is False
    assert collector._is_valid_nz_location("Southbank") is False # Found in previous leak
    assert collector._is_valid_nz_location("Footscray") is False # Found in previous leak

def test_extract_job_id(collector):
    url = "https://www.seek.co.nz/job/75043812?type=standout"
    assert collector._extract_job_id(url) == "75043812"
    
    url_no_params = "https://www.seek.co.nz/job/12345678"
    assert collector._extract_job_id(url_no_params) == "12345678"
    
    bad_url = "https://www.seek.co.nz/jobs-in-hamilton"
    assert collector._extract_job_id(bad_url) is None
