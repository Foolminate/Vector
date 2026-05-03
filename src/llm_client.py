import json
import os
from typing import Dict, Any, Optional
from google import genai
from google.genai import types
from tenacity import retry, wait_exponential, stop_after_attempt

from .database import DatabaseManager

class LLMClient:
    def __init__(self, db_manager: DatabaseManager, model_id: str):
        self.db = db_manager
        self.model_id = model_id
        
        api_key = os.environ.get("GEMINI_VECTOR_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_VECTOR_API_KEY environment variable not set.")
        
        self.client = genai.Client(api_key=api_key)

    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
    def generate_json(self, prompt: str, job_id: Optional[int] = None, action: Optional[str] = None) -> Dict[str, Any]:
        """Generates JSON content with retries and logs token usage."""
        try:
            response = self.client.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            
            # Log cost
            if response.usage_metadata:
                tokens = response.usage_metadata.total_token_count
                self._log_cost(tokens, job_id, action)
            
            data = json.loads(response.text)
            
            # Handle cases where the model wraps the response in a list
            if isinstance(data, list) and len(data) > 0:
                data = data[0]
            
            if not isinstance(data, dict):
                print(f"Warning: LLM returned non-dict JSON: {type(data)}")
                
            return data
        except Exception as e:
            print(f"LLM Error (Model: {self.model_id}): {e}")
            raise # Let tenacity handle retries

    def _log_cost(self, tokens: int, job_id: Optional[int], action: Optional[str]):
        with self.db.get_connection() as conn:
            conn.execute('''
                INSERT INTO cost_log (model, token_count, job_id, action)
                VALUES (?, ?, ?, ?)
            ''', (self.model_id, tokens, job_id, action))
            conn.commit()
