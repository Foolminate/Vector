from typing import List, Dict, Optional, Type, Any
from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings, 
    SettingsConfigDict, 
    PydanticBaseSettingsSource,
    YamlConfigSettingsSource
)
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

class CascadingStrategyConfig(BaseModel):
    enabled: bool = True
    start_priority: int = 1
    expand_on_empty: bool = True

class AppConfig(BaseSettings):
    searches: List[SearchQuery] = []
    locations: List[SearchLocation] = []
    ai_models: AIModelsConfig = Field(default_factory=AIModelsConfig)
    cascading_strategy: CascadingStrategyConfig = Field(default_factory=CascadingStrategyConfig)
    db_path: str = "data/vector.db"

    model_config = SettingsConfigDict(
        env_prefix="VECTOR_", 
        case_sensitive=False,
        env_nested_delimiter="__",
        yaml_file="SEARCH_CONFIG.yaml"
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: Type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Respect an internal environment variable for dynamic path support
        yaml_file = os.environ.get("_VECTOR_YAML_PATH", "SEARCH_CONFIG.yaml")
        return (
            init_settings,
            env_settings,
            YamlConfigSettingsSource(settings_cls, yaml_file=yaml_file),
        )

    @classmethod
    def load(cls, path: str = "SEARCH_CONFIG.yaml") -> "AppConfig":
        """
        Loads configuration with priority: ENV > YAML > Defaults.
        Supports dynamic path via internal state.
        """
        old_path = os.environ.get("_VECTOR_YAML_PATH")
        os.environ["_VECTOR_YAML_PATH"] = path
        try:
            return cls()
        finally:
            if old_path:
                os.environ["_VECTOR_YAML_PATH"] = old_path
            else:
                os.environ.pop("_VECTOR_YAML_PATH", None)

# Legacy alias to minimize immediate breakage during transition
def load_config(path: str = "SEARCH_CONFIG.yaml") -> Dict:
    """DEPRECATED: Use AppConfig.load(path) instead."""
    config = AppConfig.load(path)
    return config.model_dump()
