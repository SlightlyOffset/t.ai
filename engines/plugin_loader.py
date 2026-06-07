import os
import json
import importlib.util
import traceback
import concurrent.futures

from engines.config import get_setting
from engines.utilities import log_debug

PLUGIN_DIR = "plugins"
PLUGIN_LOAD_TIMEOUT = 5.0  # Seconds

def _load_plugin_config(plugin_path: str, is_package: bool, plugin_name: str) -> dict:
    """Attempts to load a plugin.json for a package, or <plugin_name>.json for a module."""
    if is_package:
        config_path = os.path.join(plugin_path, "plugin.json")
    else:
        # e.g. plugins/my_plugin.py -> plugins/my_plugin.json
        config_path = f"{os.path.splitext(plugin_path)[0]}.json"

    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            err_msg = f"Failed to parse config for plugin '{plugin_name}': {e}"
            log_debug("plugin_error", f"{err_msg}\n{traceback.format_exc()}")
            if get_setting("debug_mode", False) or get_setting("plugin_debug_mode", False):
                print(f"[PLUGIN ERROR] {err_msg}")
    
    return {}

def discover_and_load_plugins(context: dict) -> None:
    """
    Scans the plugins/ directory, checks disabled status, loads configuration,
    and initializes each plugin.
    """
    if not os.path.exists(PLUGIN_DIR):
        os.makedirs(PLUGIN_DIR, exist_ok=True)
        return

    disabled_plugins = get_setting("disabled_plugins", [])
    debug_mode = get_setting("debug_mode", False) or get_setting("plugin_debug_mode", False)

    for item in os.listdir(PLUGIN_DIR):
        # Skip private/hidden files
        if item.startswith("_") or item.startswith("."):
            continue

        item_path = os.path.join(PLUGIN_DIR, item)
        is_package = os.path.isdir(item_path) and os.path.exists(os.path.join(item_path, "__init__.py"))
        is_module = os.path.isfile(item_path) and item.endswith(".py")

        if not (is_package or is_module):
            continue

        plugin_name = item if is_package else item[:-3]

        if plugin_name in disabled_plugins:
            if debug_mode:
                print(f"[PLUGIN] Skipped disabled plugin: {plugin_name}")
            continue

        try:
            # 1. Load configuration
            config = _load_plugin_config(item_path, is_package, plugin_name)
            context["plugin_configs"][plugin_name] = config

            # 2. Import module
            if is_package:
                init_path = os.path.join(item_path, "__init__.py")
                spec = importlib.util.spec_from_file_location(plugin_name, init_path)
            else:
                spec = importlib.util.spec_from_file_location(plugin_name, item_path)

            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                # We need to add the plugin's dir to sys.path if it's a package so it can import its own modules
                if is_package:
                    import sys
                    if item_path not in sys.path:
                        sys.path.insert(0, item_path)
                
                spec.loader.exec_module(module)

                # 3. Initialize with timeout
                if hasattr(module, "initialize"):
                    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(module.initialize, context)
                        # Wait for the initialization to complete, or timeout
                        future.result(timeout=PLUGIN_LOAD_TIMEOUT)
                    
                    if debug_mode:
                        print(f"[PLUGIN] Successfully loaded: {plugin_name}")
                        log_debug("plugin_load", {"plugin_name": plugin_name})
                else:
                    if debug_mode:
                        print(f"[PLUGIN WARN] Plugin '{plugin_name}' has no initialize(context) function.")
                        log_debug("plugin_warn", {"plugin_name": plugin_name, "message": "no initialize function"})

        except concurrent.futures.TimeoutError:
            err_msg = f"Plugin '{plugin_name}' initialization timed out after {PLUGIN_LOAD_TIMEOUT}s."
            log_debug("plugin_error", err_msg)
            if debug_mode:
                print(f"[PLUGIN ERROR] {err_msg}")
        except Exception as e:
            err_msg = f"Failed to load plugin '{plugin_name}': {e}"
            log_debug("plugin_error", f"{err_msg}\n{traceback.format_exc()}")
            if debug_mode:
                print(f"[PLUGIN ERROR] {err_msg}")
