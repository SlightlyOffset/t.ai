import sys
import threading
import traceback
from dataclasses import dataclass
from typing import Callable, Any, Dict, List

from engines.config import get_setting
from engines.utilities import log_debug

@dataclass
class HookCallback:
    callback: Callable
    plugin_name: str
    priority: int

_hooks: Dict[str, List[HookCallback]] = {}
_registry_lock = threading.Lock()

def register_hook(hook_name: str, callback: Callable, plugin_name: str = "unknown", priority: int = 0) -> None:
    """Registers a callback for a specific hook."""
    with _registry_lock:
        if hook_name not in _hooks:
            _hooks[hook_name] = []
        _hooks[hook_name].append(HookCallback(callback, plugin_name, priority))
        # Sort by priority descending (higher priority executes first)
        _hooks[hook_name].sort(key=lambda x: x.priority, reverse=True)
        
        if get_setting("debug_mode", False) or get_setting("plugin_debug_mode", False):
            log_debug("plugin_register", {"hook_name": hook_name, "plugin_name": plugin_name, "priority": priority})

def unregister_hook(hook_name: str, callback: Callable) -> None:
    """Removes a specific callback from a hook."""
    with _registry_lock:
        if hook_name in _hooks:
            _hooks[hook_name] = [h for h in _hooks[hook_name] if h.callback != callback]

def clear_all_hooks() -> None:
    """Clears all registered hooks. Mainly used for testing."""
    with _registry_lock:
        _hooks.clear()

def get_registered_hooks() -> Dict[str, List[str]]:
    """Returns a dictionary of hook names and the plugins registered to them."""
    with _registry_lock:
        return {
            hook_name: [h.plugin_name for h in callbacks]
            for hook_name, callbacks in _hooks.items()
        }

def execute_hooks(hook_name: str, context: dict) -> None:
    """
    Executes all callbacks for a given hook name. Used for side-effects.
    Callbacks are executed in priority order (highest first).
    Exceptions in callbacks are caught and logged to prevent crashing the app.
    """
    with _registry_lock:
        callbacks = list(_hooks.get(hook_name, []))

    for hook_cb in callbacks:
        try:
            if get_setting("debug_mode", False) or get_setting("plugin_debug_mode", False):
                log_debug("plugin_execute", {"hook_name": hook_name, "plugin_name": hook_cb.plugin_name})
            hook_cb.callback(context)
        except Exception as e:
            err_msg = f"Error in plugin '{hook_cb.plugin_name}' during hook '{hook_name}': {e}"
            log_debug("plugin_error", f"{err_msg}\n{traceback.format_exc()}")
            if get_setting("debug_mode", False) or get_setting("plugin_debug_mode", False):
                print(f"[PLUGIN ERROR] {err_msg}")

def execute_pipeline(hook_name: str, data: Any, context: dict) -> Any:
    """
    Pipes data through all callbacks for a given hook name.
    Each callback receives (data, context) and MUST return the modified data.
    Callbacks are executed in priority order.
    Exceptions are caught, logged, and the data remains unmodified by that specific callback.
    """
    with _registry_lock:
        callbacks = list(_hooks.get(hook_name, []))

    current_data = data
    for hook_cb in callbacks:
        try:
            if get_setting("debug_mode", False) or get_setting("plugin_debug_mode", False):
                log_debug("plugin_execute_pipeline", {"hook_name": hook_name, "plugin_name": hook_cb.plugin_name})
            result = hook_cb.callback(current_data, context)
            if result is not None:
                current_data = result
        except Exception as e:
            err_msg = f"Error in plugin '{hook_cb.plugin_name}' during pipeline hook '{hook_name}': {e}"
            log_debug("plugin_error", f"{err_msg}\n{traceback.format_exc()}")
            if get_setting("debug_mode", False) or get_setting("plugin_debug_mode", False):
                print(f"[PLUGIN ERROR] {err_msg}")
    
    return current_data

def build_hook_context() -> dict:
    """
    Builds the shared context dictionary passed to all hooks.
    This context is mutable, allowing plugins to share state or signal core systems.
    """
    import os
    # Find project root (assumes this file is in engines/)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    return {
        "args": sys.argv,
        "headless": "--headless" in sys.argv,
        "skip_tui": False,
        "character_profile": None,
        "user_profile": None,
        "settings": None, # Will be populated if needed, or plugins can just use config.get_setting
        "history_profile_name": None,
        "session_name": None,
        "project_root": project_root,
        "plugin_configs": {},
    }
