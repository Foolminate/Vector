import json
import os
import ssl
import socket
from typing import Dict, Any, Optional, Type, TypeVar
from pydantic import BaseModel, ConfigDict
import httpx
from google import genai
from google.genai import types
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

# Robust SSL handling for Windows
try:
    import truststore
    truststore.inject_into_ssl()
    _ssl_context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
except ImportError:
    _ssl_context = None

from .database import JobRepository

T = TypeVar('T', bound=BaseModel)

def log_retry(retry_state):
    attempt = retry_state.attempt_number
    exception = retry_state.outcome.exception()
    print(f"Retrying LLM call (attempt {attempt})... Reason: {exception}")
    
    # Access the ModelAdapter instance from the retry_state
    adapter = retry_state.args[0]
    if adapter.repo:
        adapter.repo.log_action("llm_retry", f"Attempt {attempt} failed: {exception}")

class ModelAdapter:
    """
    Provider-agnostic adapter for LLM interactions.
    Currently supports Gemini, but designed for expansion.
    """
    def __init__(self, model_id: str, repo: Optional[JobRepository] = None):
        self.model_id = model_id
        self.repo = repo
        
        api_key = os.environ.get("GEMINI_VECTOR_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_VECTOR_API_KEY environment variable not set.")
        
        # Configure robust HTTP client to handle SSL handshake timeouts on Windows.
        # Increased connect timeout to 60s and total timeout to 120s.
        # Disabled HTTP/2 to prevent handshake hangs on some corporate networks.
        self._http_client = httpx.Client(
            timeout=httpx.Timeout(120.0, connect=60.0),
            verify=_ssl_context if _ssl_context else True,
            follow_redirects=True,
            http2=False,
            limits=httpx.Limits(max_connections=10, max_keepalive_connections=5)
        )
        
        self.client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                httpx_client=self._http_client
            )
        )

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=30), 
        stop=stop_after_attempt(5), 
        after=log_retry,
        # Retry on timeouts and SSL errors specifically
        retry=(
            retry_if_exception_type(httpx.TimeoutException) | 
            retry_if_exception_type(httpx.NetworkError) |
            retry_if_exception_type(ssl.SSLError) |
            retry_if_exception_type(socket.timeout)
        ),
        reraise=True
    )
    def generate_json(self, prompt: str, response_model: Type[T], task: Optional[str] = None, job_id: Optional[str] = None) -> T:
        """Generates JSON content, validates against response_model, and logs costs."""
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
        except Exception as e:
            # Re-wrap certain exceptions if needed for retry
            raise e
        
        # Log cost if repository is provided
        if self.repo and response.usage_metadata:
            usage = response.usage_metadata
            # Estimate cost (very rough, should be tuned per model)
            cost = (usage.prompt_token_count * 0.000125 + usage.candidates_token_count * 0.000375) / 1000
            self.repo.log_cost(
                model=self.model_id,
                tokens_in=usage.prompt_token_count,
                tokens_out=usage.candidates_token_count,
                cost=cost,
                task=task
            )
        
        # Parse and validate
        data = json.loads(response.text)
        
        # Handle list-wrapping if it happens
        if isinstance(data, list) and len(data) > 0:
            data = data[0]
            
        return response_model.model_validate(data)

    def generate_json_with_circuit_breaker(self, prompt: str, response_model: Type[T], task: Optional[str] = None, job_id: Optional[str] = None) -> T:
        """Wrapper for generate_json with circuit-breaker."""
        try:
            # Explicitly call ModelAdapter.generate_json to avoid recursion if overridden
            return ModelAdapter.generate_json(self, prompt, response_model, task, job_id)
        except Exception as e:
            if self.repo and job_id:
                print(f"CIRCUIT BREAKER: Permanent failure for job {job_id}")
                self.repo.update_processing_status(job_id, "failed-permanent")
                self.repo.log_action("llm_circuit_breaker", f"Permanent failure for job {job_id}: {e}")
            raise

class LLMClient(ModelAdapter):
    """Legacy Wrapper for compatibility."""
    def __init__(self, db_manager: Any, model_id: str):
        super().__init__(model_id=model_id, repo=db_manager)

    def generate_json(self, prompt, response_model=None, task=None, job_id=None, action=None):
        """Maps legacy signature to circuit-breaker implementation."""
        if response_model is None:
            # Create a dynamic model if none provided
            class DynamicResponse(BaseModel):
                model_config = ConfigDict(extra='allow')
            response_model = DynamicResponse
            
        task = task or action or "legacy"
        
        # Use ModelAdapter's circuit breaker
        result = self.generate_json_with_circuit_breaker(prompt, response_model=response_model, task=task, job_id=job_id)
        return result.model_dump()
