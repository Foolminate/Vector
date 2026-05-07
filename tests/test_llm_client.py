import pytest
import httpx
from unittest.mock import MagicMock, patch
from src.llm_client import LLMClient
from src.database import DatabaseManager

@pytest.fixture
def mock_db(tmp_path):
    db_path = tmp_path / "test_llm.db"
    return DatabaseManager(str(db_path), migrations_dir="migrations")

def test_llm_client_logs_tokens(mock_db):
    with patch('google.genai.Client') as mock_genai:
        mock_client = MagicMock()
        mock_genai.return_value = mock_client
        
        # Mock response
        mock_response = MagicMock()
        mock_response.text = '{"score": 90, "rationale": "Great"}'
        # MUST set granular tokens to avoid MagicMock in DB
        mock_response.usage_metadata.prompt_token_count = 60
        mock_response.usage_metadata.candidates_token_count = 63
        mock_response.usage_metadata.total_token_count = 123
        mock_client.models.generate_content.return_value = mock_response
        
        with patch.dict('os.environ', {'GEMINI_VECTOR_API_KEY': 'fake-key'}):
            client = LLMClient(mock_db, "test-model")
            # Legacy signature
            result = client.generate_json("test prompt", job_id=1, action="test_action")
            
            assert result["score"] == 90
            
            # Verify cost logged (v9 schema: tokens_in, tokens_out, cost, task)
            with mock_db.get_connection() as conn:
                row = conn.execute("SELECT * FROM cost_log").fetchone()
                assert row['model'] == "test-model"
                assert row['tokens_in'] == 60
                assert row['tokens_out'] == 63
                assert row['task'] == "test_action"

def test_llm_client_retries_on_error(mock_db):
    with patch('google.genai.Client') as mock_genai:
        mock_client = MagicMock()
        mock_genai.return_value = mock_client
        
        # Fail twice, succeed third time
        mock_response = MagicMock()
        mock_response.text = '{"ok": true}'
        mock_response.usage_metadata.prompt_token_count = 5
        mock_response.usage_metadata.candidates_token_count = 5
        mock_response.usage_metadata.total_token_count = 10
        
        mock_client.models.generate_content.side_effect = [
            httpx.ConnectError("API Down"),
            httpx.ConnectError("API Still Down"),
            mock_response
        ]
        
        with patch.dict('os.environ', {'GEMINI_VECTOR_API_KEY': 'fake-key'}):
            client = LLMClient(mock_db, "test-model")
            # We need to speed up the retry wait for tests
            with patch('tenacity.nap.time.sleep', return_value=None):
                result = client.generate_json("test prompt")
                assert result["ok"] is True
                assert mock_client.models.generate_content.call_count == 3

def test_llm_client_handles_list_response(mock_db):
    with patch('google.genai.Client') as mock_genai:
        mock_client = MagicMock()
        mock_genai.return_value = mock_client
        
        mock_response = MagicMock()
        mock_response.text = '[{"score": 85, "rationale": "Wrapped in list"}]'
        mock_response.usage_metadata.prompt_token_count = 25
        mock_response.usage_metadata.candidates_token_count = 25
        mock_response.usage_metadata.total_token_count = 50
        mock_client.models.generate_content.return_value = mock_response
        
        with patch.dict('os.environ', {'GEMINI_VECTOR_API_KEY': 'fake-key'}):
            client = LLMClient(mock_db, "test-model")
            result = client.generate_json("test prompt")
            
            assert isinstance(result, dict)
            assert result["score"] == 85
            assert result["rationale"] == "Wrapped in list"
