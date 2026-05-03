import os
import yaml

def load_config(config_path="SEARCH_CONFIG.yaml"):
    if not os.path.exists(config_path):
        return None
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)
