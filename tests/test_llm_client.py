import pytest
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
        mock_response.usage_metadata.total_token_count = 123
        mock_client.models.generate_content.return_value = mock_response
        
        with patch.dict('os.environ', {'GEMINI_VECTOR_API_KEY': 'fake-key'}):
            client = LLMClient(mock_db, "test-model")
            result = client.generate_json("test prompt", job_id=1, action="test_action")
            
            assert result["score"] == 90
            
            # Verify cost logged
            with mock_db.get_connection() as conn:
                row = conn.execute("SELECT * FROM cost_log").fetchone()
                assert row['model'] == "test-model"
                assert row['token_count'] == 123
                assert row['job_id'] == 1
                assert row['action'] == "test_action"

def test_llm_client_retries_on_error(mock_db):
    with patch('google.genai.Client') as mock_genai:
        mock_client = MagicMock()
        mock_genai.return_value = mock_client
        
        # Fail twice, succeed third time
        mock_response = MagicMock()
        mock_response.text = '{"ok": true}'
        mock_response.usage_metadata.total_token_count = 10
        
        mock_client.models.generate_content.side_effect = [
            Exception("API Down"),
            Exception("API Still Down"),
            mock_response
        ]
        
        with patch.dict('os.environ', {'GEMINI_VECTOR_API_KEY': 'fake-key'}):
            client = LLMClient(mock_db, "test-model")
            # We need to speed up the retry wait for tests
            with patch('tenacity.nap.time.sleep', return_value=None):
                result = client.generate_json("test prompt")
                assert result["ok"] is True
                assert mock_client.models.generate_content.call_count == 3
