from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml
import os

class SearchLocation(BaseModel):
    name: str
    slug: str
    priority: int = 1

class SearchQuery(BaseModel):
    keywords: str
    priority: int = 1

class AIModelsConfig(BaseModel):
    sorter: str = "gemini-3-flash-preview"
    evaluator: str = "gemini-3.1-pro-preview"

class AppConfig(BaseSettings):
    searches: List[SearchQuery] = []
    locations: List[SearchLocation] = []
    ai_models: AIModelsConfig = Field(default_factory=AIModelsConfig)
    db_path: str = "data/vector.db"

    model_config = SettingsConfigDict(env_prefix="VECTOR_", case_sensitive=False)

    @classmethod
    def load(cls, path: str = "SEARCH_CONFIG.yaml") -> "AppConfig":
        data = {}
        if os.path.exists(path):
            with open(path, 'r') as f:
                data = yaml.safe_load(f) or {}
        
        return cls(**data)

# Legacy alias to minimize immediate breakage during transition
def load_config() -> Dict:
    """DEPRECATED: Use AppConfig.load() instead."""
    config = AppConfig.load()
    return config.model_dump()
