import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from src.collector import SeekCollector
from src.models import RawJobData

@pytest.fixture
def mock_db():
    return MagicMock()

@pytest.fixture
def mock_config():
    config = MagicMock()
    config.searches = []
    config.locations = []
    return config

@pytest.mark.asyncio
async def test_detect_bot_blocked_403(mock_db, mock_config):
    collector = SeekCollector(mock_db, mock_config)
    
    mock_page = AsyncMock()
    mock_response = MagicMock()
    mock_response.status = 403
    mock_page.goto.return_value = mock_response
    mock_page.query_selector.return_value = None
    
    # We need to mock scrape_search_results or the parts it uses
    result = await collector.scrape_search_results(mock_page, "https://test.com")
    
    assert result == 0
    mock_db.log_action.assert_called_with("bot_blocked", "403 Forbidden at https://test.com")

@pytest.mark.asyncio
async def test_detect_bot_blocked_captcha(mock_db, mock_config):
    collector = SeekCollector(mock_db, mock_config)
    
    mock_page = AsyncMock()
    mock_page.goto.return_value = MagicMock(status=200)
    mock_page.query_selector.return_value = None
    mock_page.content.return_value = "<html><body>This is a CAPTCHA page</body></html>"
    
    result = await collector.scrape_search_results(mock_page, "https://test.com")
    
    assert result == 0
    mock_db.log_action.assert_called_with("bot_blocked", "CAPTCHA detected at https://test.com")

@pytest.mark.asyncio
async def test_scrape_job_details_failure_logging(mock_db, mock_config):
    collector = SeekCollector(mock_db, mock_config)
    
    mock_context = AsyncMock()
    mock_page = AsyncMock()
    mock_context.new_page.return_value = mock_page
    mock_page.goto.side_effect = Exception("Timeout")
    
    result = await collector.scrape_job_details(mock_context, "https://test.com/job/1")
    
    assert result is None
    mock_db.log_action.assert_called_with("scrape_failed", "Error scraping https://test.com/job/1: Timeout")

@pytest.mark.asyncio
async def test_scrape_search_results_success(mock_db, mock_config):
    collector = SeekCollector(mock_db, mock_config)
    collector.parser = MagicMock()
    collector.parser.parse_search_results.return_value = [
        RawJobData(title="Job 1", url="http://test.com/1", seek_job_id="1", location="Auckland")
    ]
    
    # Mock is_already_scraped
    collector.is_already_scraped = MagicMock(return_value=False)
    
    mock_page = AsyncMock()
    mock_page.goto.return_value = MagicMock(status=200)
    mock_page.query_selector.return_value = MagicMock()
    mock_page.evaluate.return_value = {
        "results": {
            "relatedSearches": [{"keywords": "Related", "totalJobs": 10}],
            "locationWhere": "Auckland"
        }
    }
    
    # Mock scrape_job_details to return something
    with patch.object(collector, "scrape_job_details", new_callable=AsyncMock) as mock_details:
        mock_details.return_value = "Full job description"
        
        result = await collector.scrape_search_results(mock_page, "https://test.com")
        
        assert result == 1
        mock_db.log_suggestion.assert_called_with("Related", "Auckland", 10)
        mock_db.upsert_job.assert_called_once()

def test_is_already_scraped_logic(mock_db, mock_config):
    """Verify is_already_scraped hits the DB correctly."""
    collector = SeekCollector(mock_db, mock_config)
    
    mock_conn = MagicMock()
    mock_db.get_connection.return_value.__enter__.return_value = mock_conn
    
    # Test case 1: Found
    mock_conn.cursor.return_value.fetchone.return_value = {"id": 1}
    assert collector.is_already_scraped("exists") is True
    
    # Test case 2: Not found
    mock_conn.cursor.return_value.fetchone.return_value = None
    assert collector.is_already_scraped("missing") is False
    
    # Test case 3: Empty ID
    assert collector.is_already_scraped("") is False

@pytest.mark.asyncio
async def test_scrape_search_results_with_pipeline(mock_db, mock_config):
    mock_pipeline = MagicMock()
    collector = SeekCollector(mock_db, mock_config, pipeline=mock_pipeline)
    collector.parser = MagicMock()
    collector.parser.parse_search_results.return_value = [
        RawJobData(title="Job 1", url="http://test.com/1", seek_job_id="1", location="Auckland")
    ]
    collector.is_already_scraped = MagicMock(return_value=False)
    
    mock_page = AsyncMock()
    mock_page.goto.return_value = MagicMock(status=200)
    mock_page.query_selector.return_value = MagicMock()
    mock_page.evaluate.return_value = {}
    
    with patch.object(collector, "scrape_job_details", new_callable=AsyncMock) as mock_details:
        mock_details.return_value = "Full job description"
        await collector.scrape_search_results(mock_page, "https://test.com")
        
        mock_pipeline.push.assert_called_with("1")

def test_extract_job_id_deprecated(mock_db, mock_config):
    collector = SeekCollector(mock_db, mock_config)
    # This calls parser._extract_job_id
    collector.parser._extract_job_id = MagicMock(return_value="123")
    assert collector._extract_job_id("url") == "123"

def test_clean_url(mock_db, mock_config):
    collector = SeekCollector(mock_db, mock_config)
    assert collector._clean_url("http://test.com?p=1") == "http://test.com"
    assert collector._clean_url("http://test.com") == "http://test.com"

@pytest.mark.asyncio
async def test_scrape_main_loop(mock_db, mock_config):
    """Verify high-level scrape loop iterates over searches and locations."""
    mock_config.searches = [MagicMock(keywords="Dev", priority=1)]
    mock_config.locations = [MagicMock(name="Akl", slug="akl", priority=1)]
    
    collector = SeekCollector(mock_db, mock_config)
    
    with patch("src.collector.async_playwright") as mock_p:
        mock_playwright = mock_p.return_value.__aenter__.return_value
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        
        mock_playwright.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        
        with patch.object(collector, "scrape_search_results", new_callable=AsyncMock) as mock_scrape:
            mock_scrape.return_value = 5
            
            await collector.scrape(limit=5)
            
            mock_scrape.assert_called()
            assert mock_browser.close.called

@pytest.mark.asyncio
async def test_scrape_limits(mock_db, mock_config):
    """Verify that scrape respects the job limit."""
    mock_config.searches = [MagicMock(keywords="Dev", priority=1)]
    mock_config.locations = [MagicMock(name="Akl", slug="akl", priority=1)]
    collector = SeekCollector(mock_db, mock_config)
    
    with patch("src.collector.async_playwright") as mock_p:
        mock_playwright = mock_p.return_value.__aenter__.return_value
        mock_context = AsyncMock()
        mock_playwright.chromium.launch.return_value = AsyncMock()
        mock_browser = mock_playwright.chromium.launch.return_value
        mock_browser.new_context.return_value = mock_context
        
        with patch.object(collector, "scrape_search_results", new_callable=AsyncMock) as mock_scrape:
            mock_scrape.return_value = 10
            await collector.scrape(limit=5)
            # Should have called scrape_search_results but limited logic checked before second iteration if any
            mock_scrape.assert_called()

@pytest.mark.asyncio
async def test_scrape_job_details_success(mock_db, mock_config):
    collector = SeekCollector(mock_db, mock_config)
    mock_context = AsyncMock()
    mock_page = AsyncMock()
    mock_context.new_page.return_value = mock_page
    mock_page.content.return_value = "<html>Job Details</html>"
    collector.parser.parse_job_details = MagicMock(return_value="Clean Text")
    
    result = await collector.scrape_job_details(mock_context, "http://test.com/job")
    assert result == "Clean Text"

def test_is_valid_nz_location_edge_cases(mock_db, mock_config):
    collector = SeekCollector(mock_db, mock_config)
    assert collector._is_valid_nz_location(None) is True
    assert collector._is_valid_nz_location("") is True

def test_save_job_deprecated(mock_db, mock_config):
    collector = SeekCollector(mock_db, mock_config)
    collector.save_job("T", "C", "L", "U", "RT", "ID")
    mock_db.upsert_job.assert_called()

@pytest.mark.asyncio
async def test_scrape_search_results_sem_scrape_failure(mock_db, mock_config):
    collector = SeekCollector(mock_db, mock_config)
    collector.parser = MagicMock()
    collector.parser.parse_search_results.return_value = [
        RawJobData(title="Job 1", url="http://test.com/1", seek_job_id="1", location="Auckland")
    ]
    collector.is_already_scraped = MagicMock(return_value=False)
    
    mock_page = AsyncMock()
    mock_page.goto.return_value = MagicMock(status=200)
    mock_page.query_selector.return_value = MagicMock()
    mock_page.evaluate.return_value = {}
    
    with patch.object(collector, "scrape_job_details", new_callable=AsyncMock) as mock_details:
        mock_details.return_value = None # Failure
        result = await collector.scrape_search_results(mock_page, "https://test.com")
        assert result == 0

@pytest.mark.asyncio
async def test_scrape_search_results_with_limit(mock_db, mock_config):
    collector = SeekCollector(mock_db, mock_config)
    collector.parser = MagicMock()
    # 3 jobs found
    collector.parser.parse_search_results.return_value = [
        RawJobData(title=f"J{i}", url=f"http://t.com/{i}", seek_job_id=str(i), location="Akl") for i in range(3)
    ]
    collector.is_already_scraped = MagicMock(return_value=False)
    
    mock_page = AsyncMock()
    mock_page.goto.return_value = MagicMock(status=200)
    mock_page.query_selector.return_value = MagicMock()
    mock_page.evaluate.return_value = {}
    
    with patch.object(collector, "scrape_job_details", new_callable=AsyncMock) as mock_details:
        mock_details.return_value = "Text"
        # Request limit of 1
        result = await collector.scrape_search_results(mock_page, "https://test.com", limit=1)
        assert result == 1
