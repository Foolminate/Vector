import pytest
from unittest.mock import MagicMock, patch
from src.llm_client import ModelAdapter
from pydantic import BaseModel

class TriageResult(BaseModel):
    score: int
    reason: str

def test_model_adapter_gemini_mock():
    """Test that ModelAdapter correctly handles a mock Gemini response."""
    # Mocking the genai.Client
    with patch("google.genai.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_response = MagicMock()
        mock_response.text = '{"score": 85, "reason": "Great match"}'
        mock_response.usage_metadata.total_token_count = 100
        mock_client.models.generate_content.return_value = mock_response
        
        adapter = ModelAdapter(model_id="test-model")
        result = adapter.generate_json(
            prompt="Test prompt",
            response_model=TriageResult
        )
        
        assert result.score == 85
        assert result.reason == "Great match"
        assert isinstance(result, TriageResult)

def test_model_adapter_error_handling():
    """Test that ModelAdapter handles errors gracefully."""
    with patch("google.genai.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        mock_client.models.generate_content.side_effect = Exception("API Down")
        
        adapter = ModelAdapter(model_id="test-model")
        with pytest.raises(Exception, match="API Down"):
            adapter.generate_json(prompt="Test", response_model=TriageResult)
