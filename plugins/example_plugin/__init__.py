"""
Example plugin to demonstrate the new plugin system.
"""

from engines.hooks import register_hook
from engines.utilities import log_debug
import logging

# Set up simple logging for the plugin
logger = logging.getLogger("t.ai.plugins.example")
logger.setLevel(logging.INFO)
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(ch)


def initialize(context):
    """
    Entry point for the plugin.
    Registers hooks based on the config.
    """
    plugin_configs = context.get("plugin_configs", {})
    my_config = plugin_configs.get("example_plugin", {})
    
    if my_config.get("enabled", True):
        register_hook("on_startup", on_startup, plugin_name="example_plugin")
        register_hook("on_user_message", on_user_message, plugin_name="example_plugin", priority=50)
        register_hook("before_prompt_build", before_prompt_build, plugin_name="example_plugin")
        prefix = my_config.get('prefix', '[EXAMPLE]')
        logger.info(f"{prefix} Example plugin initialized successfully!")
        log_debug("example_plugin_init", {"prefix": prefix})


def on_startup(context):
    logger.info("Application starting up! (from example plugin)")
    log_debug("example_plugin_startup", {"status": "started"})


def on_user_message(user_input, context):
    """
    Modify the user input before it goes into the history or LLM.
    """
    plugin_configs = context.get("plugin_configs", {})
    prefix = plugin_configs.get("example_plugin", {}).get("prefix", "[EXAMPLE]")
    
    logger.info(f"Intercepted user message. Length: {len(user_input)}")
    log_debug("example_plugin_user_message", {"length": len(user_input)})
    return user_input


def before_prompt_build(messages, context):
    """
    View the messages before they are sent to the LLM.
    """
    logger.info(f"About to build prompt with {len(messages)} messages in history.")
    log_debug("example_plugin_before_prompt_build", {"message_count": len(messages)})
    return messages
