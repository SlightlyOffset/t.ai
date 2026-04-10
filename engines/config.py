"""
Configuration management for global application settings.
Handles reading and writing to settings.json.
"""

import json
import os
from dotenv import load_dotenv

# Load .env file if it exists
load_dotenv()

# Path to the global settings file
SETTINGS_FILE = "settings.json"

def load_settings():
    """
    Loads all settings from the JSON file.
    
    Returns:
        dict: The loaded settings, or an empty dict if the file is missing/invalid.
    """
    if not os.path.exists(SETTINGS_FILE):
        return {}
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}

def get_setting(key, default=None):
    """
    Retrieves a specific setting by key.
    Prioritizes environment variables (UPPERCASE) over the JSON settings.
    
    Args:
        key (str): The setting key to find.
        default: The value to return if the key doesn't exist.
        
    Returns:
        The value of the setting or the default.
    """
    # Check env first (map 'remote_llm_url' to 'REMOTE_LLM_URL')
    env_val = os.getenv(key.upper())
    if env_val is not None:
        # Simple boolean/int conversion for env vars
        if env_val.lower() == "true": return True
        if env_val.lower() == "false": return False
        try:
            if "." in env_val: return float(env_val)
            return int(env_val)
        except ValueError:
            return env_val

    settings = load_settings()
    return settings.get(key, default)

def update_setting(key, value):
    """
    Updates a specific setting and saves it back to the file atomically.
    
    Args:
        key (str): The setting key to update.
        value: The new value for the setting.
        
    Returns:
        bool: True if the update was successful, False otherwise.
    """
    from engines.utilities import save_json_atomic
    settings = load_settings()
    settings[key] = value
    return save_json_atomic(SETTINGS_FILE, settings)
