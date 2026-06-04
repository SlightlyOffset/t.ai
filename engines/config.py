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
    Falls back to settings.json.bak and heals settings.json if the primary file is missing or invalid.
    
    Returns:
        dict: The loaded settings, or an empty dict if the file is missing/invalid.
    """
    settings = None
    # 1. Try loading primary file
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            settings = json.load(f)
    except FileNotFoundError:
        pass
    except (json.JSONDecodeError, IOError):
        pass

    # 2. Try loading backup file and heal if primary failed/missing
    if settings is None:
        bak_file = SETTINGS_FILE + ".bak"
        try:
            with open(bak_file, "r", encoding="utf-8") as f:
                settings = json.load(f)
            
            # Heal primary
            from engines.utilities import save_json_atomic
            save_json_atomic(SETTINGS_FILE, settings)
        except FileNotFoundError:
            pass
        except (json.JSONDecodeError, IOError):
            pass

    return settings if settings is not None else {}

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
    val = None
    if env_val is not None:
        # Simple boolean/int conversion for env vars
        if env_val.lower() == "true": val = True
        elif env_val.lower() == "false": val = False
        else:
            try:
                if "." in env_val: val = float(env_val)
                else: val = int(env_val)
            except ValueError:
                val = env_val
    else:
        settings = load_settings()
        val = settings.get(key, default)

    # Security Validation for remote URLs (VULN-004)
    if key in ["remote_llm_url", "remote_tts_url"] and val:
        if isinstance(val, str) and not val.startswith("https://"):
            # We reject non-HTTPS URLs for remote services to prevent PII leaks
            from colorama import Fore
            warning_msg = (
                f"[SECURITY WARNING] Insecure remote URL rejected for "
                f"'{key}': {val}. Only HTTPS is allowed."
            )
            print(Fore.RED + warning_msg + Fore.RESET)
            return None

    return val

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

def update_settings(updates):
    """
    Updates multiple settings at once and saves them back to the file atomically.
    
    Args:
        updates (dict): A dictionary of key-value pairs to update.
        
    Returns:
        bool: True if the update was successful, False otherwise.
    """
    from engines.utilities import save_json_atomic
    settings = load_settings()
    for key, value in updates.items():
        settings[key] = value
    return save_json_atomic(SETTINGS_FILE, settings)


def get_active_session(character_name: str) -> str:
    """
    Retrieves the active session name for a specific character profile.
    Falls back to global 'current_history_session' or 'default'.
    
    Args:
        character_name (str): Name of the character profile.
        
    Returns:
        str: Active session name.
    """
    from engines.utilities import sanitize_profile_name
    if not character_name:
        return get_setting("current_history_session", "default")
    
    safe_char = sanitize_profile_name(character_name) or "session"
    char_session = get_setting(f"session_{safe_char}")
    if char_session is not None:
        return char_session
        
    # Fallback to legacy global setting
    global_session = get_setting("current_history_session")
    if global_session is not None:
        # Migrate/save it to the character setting
        update_setting(f"session_{safe_char}", global_session)
        return global_session
        
    return "default"


def set_active_session(character_name: str, session_name: str) -> bool:
    """
    Updates the active session name for a specific character profile.
    Also updates the legacy global setting to maintain compatibility.
    
    Args:
        character_name (str): Name of the character profile.
        session_name (str): Name of the session.
        
    Returns:
        bool: True if successful, False otherwise.
    """
    from engines.utilities import sanitize_profile_name
    updates = {"current_history_session": session_name}
    if character_name:
        safe_char = sanitize_profile_name(character_name) or "session"
        updates[f"session_{safe_char}"] = session_name
    return update_settings(updates)


