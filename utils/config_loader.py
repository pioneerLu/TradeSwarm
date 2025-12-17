import os
import yaml
from dotenv import dotenv_values

def load_config() -> dict:
    """
    Loads configuration from .env.example and config/config.yaml.
    Environment variables from .env.example take precedence over config.yaml.
    
    Returns:
        dict: The merged configuration dictionary.
    """
    # Define paths
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    env_path = os.path.join(project_root, '.env')
    config_path = os.path.join(project_root, 'config', 'config.yaml')

    # Load YAML config
    config = {}
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}

    # Load .env.example values
    env_vars = dotenv_values(env_path)

    # Ensure 'llm' section exists
    if 'llm' not in config:
        config['llm'] = {}

    # Mapping table (Env Key -> Config Section, Config Key)
    mapping = {
        'MODEL_NAME': ('llm', 'model_name'),
        'DASHSCOPE_API_KEY': ('llm', 'api_key'),
        'BASE_URL': ('llm', 'base_url'),
    }

    # Apply overrides
    for env_key, (section, key) in mapping.items():
        val = env_vars.get(env_key)
        if val:
            if section not in config:
                config[section] = {}
            config[section][key] = val

    return config

