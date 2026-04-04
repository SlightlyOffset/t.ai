import os
from engines.config import get_setting

def test_env_override(monkeypatch):
    # Test setting exists in settings.json as "rp"
    # We override it via environment
    monkeypatch.setenv("INTERACTION_MODE", "casual")
    
    mode = get_setting("interaction_mode")
    assert mode == "casual"

def test_env_boolean_conversion(monkeypatch):
    monkeypatch.setenv("DEBUG_MODE", "true")
    assert get_setting("debug_mode") is True
    
    monkeypatch.setenv("DEBUG_MODE", "false")
    assert get_setting("debug_mode") is False

def test_env_numeric_conversion(monkeypatch):
    monkeypatch.setenv("MEMORY_LIMIT", "50")
    assert get_setting("memory_limit") == 50
