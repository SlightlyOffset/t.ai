import pytest
from unittest.mock import patch
from engines.plugin_loader import discover_and_load_plugins
from engines.hooks import build_hook_context, clear_all_hooks, get_registered_hooks

@pytest.fixture(autouse=True)
def cleanup_hooks():
    clear_all_hooks()
    yield
    clear_all_hooks()

@patch('engines.plugin_loader.get_setting')
def test_plugin_loader(mock_get_setting):
    mock_get_setting.side_effect = lambda key, default=None: [] if key == "disabled_plugins" else default

    context = build_hook_context()
    discover_and_load_plugins(context)
    
    # example_plugin should be loaded and its hooks registered
    hooks = get_registered_hooks()
    assert "on_startup" in hooks
    assert "example_plugin" in hooks["on_startup"]
    
    assert "on_user_message" in hooks
    assert "example_plugin" in hooks["on_user_message"]
    
    assert "before_prompt_build" in hooks
    assert "example_plugin" in hooks["before_prompt_build"]
    
    # Check that config was loaded into context
    assert "example_plugin" in context["plugin_configs"]
    assert context["plugin_configs"]["example_plugin"]["enabled"] is True
