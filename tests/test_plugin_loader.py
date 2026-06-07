import pytest
from engines.plugin_loader import discover_and_load_plugins
from engines.hooks import build_hook_context, clear_all_hooks, get_registered_hooks

@pytest.fixture(autouse=True)
def cleanup_hooks():
    clear_all_hooks()
    yield
    clear_all_hooks()

def test_plugin_loader():
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
