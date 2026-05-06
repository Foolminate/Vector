import json
import os
from typing import Dict, Any, Optional, Type, TypeVar
from pydantic import BaseModel
from google import genai
from google.genai import types
from tenacity import retry, wait_exponential, stop_after_attempt

from .database import JobRepository

T = TypeVar('T', bound=BaseModel)

def log_retry(retry_state):
    print(f"Retrying LLM call (attempt {retry_state.attempt_number})... Reason: {retry_state.outcome.exception()}")

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
        
        self.client = genai.Client(
            api_key=api_key,
            http_options={'timeout': 60.0}
        )

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=30), 
        stop=stop_after_attempt(5), 
        after=log_retry,
        reraise=True
    )
    def generate_json(self, prompt: str, response_model: Type[T], task: Optional[str] = None) -> T:
        """
        Generates JSON content, validates against response_model, 
        and logs costs.
        """
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            
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
            
        except Exception as e:
            raise

class LLMClient(ModelAdapter):
    """Legacy Wrapper for compatibility."""
    def __init__(self, db_manager: Any, model_id: str):
        super().__init__(model_id=model_id, repo=db_manager)

    def generate_json(self, prompt, response_model=None, task=None, job_id=None, action=None):
        """Maps legacy signature to ModelAdapter.generate_json."""
        if response_model is None:
            # Create a dynamic model if none provided
            class DynamicResponse(BaseModel):
                class Config:
                    extra = 'allow'
            response_model = DynamicResponse
            
        task = task or action or "legacy"
        # We don't use job_id directly here, ModelAdapter logs it via repo if needed
        # but ModelAdapter.log_cost doesn't take job_id currently.
        
        result = super().generate_json(prompt, response_model=response_model, task=task)
        return result.model_dump()
