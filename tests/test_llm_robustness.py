import pytest
from unittest.mock import MagicMock, patch
from src.llm_client import ModelAdapter
from src.models import TriageResult
from tenacity import RetryError
import sqlite3

@pytest.fixture
def mock_repo():
    repo = MagicMock()
    return repo

def test_llm_retries_logged_to_audit_log(mock_repo):
    adapter = ModelAdapter(model_id="test-model", repo=mock_repo)
    import httpx
    
    with patch.object(adapter.client.models, 'generate_content') as mock_gen:
        # Fail 2 times then succeed
        mock_gen.side_effect = [
            httpx.ConnectError("Fail 1"),
            httpx.ReadTimeout("Fail 2"),
            MagicMock(text='{"score": 85, "reason": "Good"}', usage_metadata=None)
        ]
        
        adapter.generate_json("Prompt", TriageResult)
        
        # Should be called twice for retries
        # Filter log_action calls for "llm_retry"
        retry_calls = [call for call in mock_repo.log_action.call_args_list if call.args[0] == "llm_retry"]
        assert len(retry_calls) == 2
        assert "Attempt 1" in retry_calls[0].args[1]
        assert "Fail 1" in retry_calls[0].args[1]
        assert "Attempt 2" in retry_calls[1].args[1]
        assert "Fail 2" in retry_calls[1].args[1]

def test_llm_permanent_failure_updates_job_status(mock_repo):
    adapter = ModelAdapter(model_id="test-model", repo=mock_repo)
    
    with patch.object(adapter.client.models, 'generate_content') as mock_gen:
        # Always fail
        mock_gen.side_effect = Exception("Permanent Fail")
        
        # We need a job_id for the circuit breaker to mark it as failed-permanent
        with pytest.raises(Exception): # The ultimate exception will still be raised
             adapter.generate_json_with_circuit_breaker("Prompt", TriageResult, job_id="job_999")
        
        mock_repo.update_processing_status.assert_called_with("job_999", "failed-permanent")
        mock_repo.log_action.assert_any_call("llm_circuit_breaker", "Permanent failure for job job_999: Permanent Fail")

def test_llm_retries_on_ssl_timeout(mock_repo):
    """Verify that the adapter retries on SSL handshake timeouts."""
    adapter = ModelAdapter(model_id="test-model", repo=mock_repo)
    import ssl
    import httpx
    
    with patch.object(adapter.client.models, 'generate_content') as mock_gen:
        # Simulate SSL handshake timeout (the user's reported error)
        mock_gen.side_effect = [
            ssl.SSLError("_ssl.c:1011: The handshake operation timed out"),
            httpx.ConnectTimeout("Connect timeout"),
            MagicMock(text='{"score": 70, "reason": "Retried"}', usage_metadata=None)
        ]
        
        result = adapter.generate_json("Prompt", TriageResult)
        assert result.score == 70
        
        retry_calls = [call for call in mock_repo.log_action.call_args_list if call.args[0] == "llm_retry"]
        assert len(retry_calls) == 2
        assert "handshake operation timed out" in retry_calls[0].args[1]

def test_llm_retries_on_socket_timeout(mock_repo):
    """Verify that the adapter retries on raw socket timeouts."""
    adapter = ModelAdapter(model_id="test-model", repo=mock_repo)
    import socket
    
    with patch.object(adapter.client.models, 'generate_content') as mock_gen:
        mock_gen.side_effect = [
            socket.timeout("Socket timeout"),
            MagicMock(text='{"score": 60, "reason": "Socket recovered"}', usage_metadata=None)
        ]
        
        # Speed up retry
        with patch('tenacity.nap.time.sleep', return_value=None):
            result = adapter.generate_json("Prompt", TriageResult)
            assert result.score == 60
            
            retry_calls = [call for call in mock_repo.log_action.call_args_list if call.args[0] == "llm_retry"]
            assert len(retry_calls) == 1
            assert "Socket timeout" in retry_calls[0].args[1]
