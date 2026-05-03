import os
import yaml
import pytest
from src.config_loader import load_config

def test_load_config_with_ai_models(tmp_path):
    config_data = {
        "ai_models": {
            "sorter": "test-sorter-model",
            "evaluator": "test-evaluator-model"
        },
        "locations": [
            {"name": "Hamilton", "slug": "Hamilton-Waikato"}
        ]
    }
    config_file = tmp_path / "test_config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)
    
    config = load_config(str(config_file))
    assert config["ai_models"]["sorter"] == "test-sorter-model"
    assert config["locations"][0]["slug"] == "Hamilton-Waikato"

def test_load_config_missing_file():
    config = load_config("non_existent.yaml")
    assert config is None
