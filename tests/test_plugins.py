import pytest
from engines.hooks import (
    register_hook, 
    execute_hooks, 
    execute_pipeline, 
    build_hook_context,
    clear_all_hooks
)

@pytest.fixture(autouse=True)
def cleanup_hooks():
    # Setup
    clear_all_hooks()
    yield
    # Teardown
    clear_all_hooks()

def test_hook_registry_execution():
    context = build_hook_context()
    
    # Test state
    test_state = {"called_A": False, "called_B": False}
    
    def hook_a(ctx):
        test_state["called_A"] = True
        
    def hook_b(ctx):
        test_state["called_B"] = True
        
    register_hook("on_startup", hook_a, priority=100)
    register_hook("on_startup", hook_b, priority=50)
    
    execute_hooks("on_startup", context)
    
    assert test_state["called_A"] is True
    assert test_state["called_B"] is True


def test_hook_pipeline():
    context = build_hook_context()
    
    def append_a(data, ctx):
        return data + "A"
        
    def append_b(data, ctx):
        return data + "B"
        
    # Higher priority number runs first
    register_hook("before_prompt_build", append_b, priority=200)
    register_hook("before_prompt_build", append_a, priority=100)
    
    result = execute_pipeline("before_prompt_build", "Start", context)
    
    # append_b runs first (priority 200), then append_a (priority 100)
    assert result == "StartBA"


def test_hook_pipeline_error_handling():
    context = build_hook_context()
    
    def append_a(data, ctx):
        return data + "A"
        
    def failing_hook(data, ctx):
        raise ValueError("Simulated failure")
        
    def append_c(data, ctx):
        return data + "C"
        
    register_hook("test_pipe", append_a, priority=100)
    register_hook("test_pipe", failing_hook, priority=200)
    register_hook("test_pipe", append_c, priority=300)
    
    result = execute_pipeline("test_pipe", "Start", context)
    
    # failing_hook is skipped, C (300) runs first, then A (100)
    assert result == "StartCA"
