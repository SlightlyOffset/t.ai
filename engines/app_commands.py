"""
Internal CLI command handler for the application.
Processes commands starting with '//' to manage settings, history, and app state.
"""
# Standard library imports
import sys
import os
import shutil
import re
import json

# Third-party imports
from colorama import Fore, init

# Local imports
from engines.config import update_setting, get_setting
from engines.utilities import pick_history
from engines.utilities import pick_profile
from engines.utilities import pick_user_profile, render_historical_message # Import render_historical_message
from engines.memory_v2 import memory_manager # Import memory_manager
from engines.character_importer import import_character

# Initialize colorama
init(autoreset=True)

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Path to conversation history files
HISTORY_PATH = "history/"

# List of settings keys that should be masked in the UI for security
SENSITIVE_KEYS = [
    "hf_token",
    "ngrok_token",
    "remote_llm_url",
    "remote_tts_url",
    "elevenlabs_api_key",
    "openai_api_key",
    "github_token"
]

class RestartRequested(Exception):
    """Exception raised to signal the main loop to restart the application."""
    pass

class RegenerateRequested(Exception):
    """Exception raised to signal the TUI to regenerate the last AI message."""
    pass

class CompressRequested(Exception):
    """Exception raised to signal the TUI to manually compress conversation context."""
    pass

class RewindRequested(Exception):
    """Exception raised to signal the TUI to rewind history to a message index."""
    def __init__(self, message_number: int):
        super().__init__(f"Rewind requested to message {message_number}")
        self.message_number = message_number

class SettingsRequested(Exception):
    """Exception raised to signal the TUI to open the settings screen."""
    pass

def app_commands(ops: str, suppress_output: bool = False):
    """
    Dispatcher for internal operational commands.

    Args:
        ops (str): The raw command input (e.g., '//help').
        suppress_output (bool): If True, returns (success, message) instead of printing.

    Returns:
        bool or tuple: True/False if not suppressed, or (bool, str) if suppressed.
    """
    output_buffer = []

    def _log(msg, color=Fore.WHITE):
        if suppress_output:
            # Strip ANSI codes for the TUI message
            clean_msg = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', str(msg))
            output_buffer.append(clean_msg)
        else:
            print(color + str(msg))

    def _help():
        """Lists all available commands."""
        _log("[AVAILABLE COMMANDS]", Fore.YELLOW)
        for cmd, func in cmds.items():
            doc = func.__doc__ if func.__doc__ else ""
            desc = doc.split("\n")[0] if doc else ""
            if not desc:
                if cmd == "//mode":
                    desc = "Shortcut to toggle interaction mode (RP / Casual)."
                elif cmd.startswith("//toggle_"):
                    setting_name = cmd.replace("//toggle_", "")
                    desc = f"Shortcut to toggle '{setting_name}' setting."
                elif cmd == "//reset_all":
                    desc = "Shortcut to wipe all chat history files."
                elif cmd == "//reset_rel":
                    desc = "Shortcut to reset active profile relationship score."
            _log(f"  {cmd:<25} - {desc}", Fore.CYAN)


    def _exit():
        """Exits the application."""
        _log("[SYSTEM] Exiting application...", Fore.YELLOW)
        sys.exit(0)

    def _show_settings():
        """Displays current system settings from settings.json."""
        from engines.config import load_settings
        settings = load_settings()
        _log("[CURRENT SETTINGS]", Fore.YELLOW)
        for key, value in settings.items():
            display_value = value
            # Mask sensitive values to prevent accidental exposure (VULN-005)
            if key.lower() in SENSITIVE_KEYS or any(s in key.lower() for s in ["token", "api_key", "secret"]):
                display_value = "********"
            _log(f"  {key}: {display_value}", Fore.CYAN)

    def _toggle(args=None):
        """Toggles a boolean setting. Usage: //toggle [tts|tts_tag|speak|narration|command|clear|recap|errors|privacy|debug|mode]"""
        if not args or not args.strip():
            _log("[SYSTEM] Usage: //toggle [tts|tts_tag|speak|narration|command|clear|recap|errors|privacy|debug|mode]", Fore.YELLOW)
            _log("Available settings to toggle:", Fore.YELLOW)
            _log("  tts       - Text-to-Speech master enable", Fore.CYAN)
            _log("  tts_tag   - Show TTS engine tag in chat", Fore.CYAN)
            _log("  speak     - Character speaking toggle", Fore.CYAN)
            _log("  narration - Read narration toggle", Fore.CYAN)
            _log("  command   - AI system command execution toggle", Fore.CYAN)
            _log("  clear     - Clear screen on start toggle", Fore.CYAN)
            _log("  recap     - Auto recap at startup toggle", Fore.CYAN)
            _log("  errors    - Error messages suppression toggle", Fore.CYAN)
            _log("  privacy   - Privacy Mode (PII redaction) toggle", Fore.CYAN)
            _log("  debug     - Debug mode toggle", Fore.CYAN)
            _log("  mode      - Interaction mode toggle (RP / Casual)", Fore.CYAN)
            return

        choice = args.strip().lower()
        if choice == "mode":
            current_mode = get_setting("interaction_mode", "rp")
            new_mode = "casual" if current_mode == "rp" else "rp"
            update_setting("interaction_mode", new_mode)
            _log(f"[SYSTEM] Interaction mode set to {new_mode.upper()}.", Fore.GREEN)
            return

        toggle_map = {
            "tts": (
                "tts_enabled", 
                "[SYSTEM] Text-to-Speech enabled.", 
                "[SYSTEM] Text-to-Speech disabled.", 
                False
            ),
            "tts_tag": (
                "show_tts_engine", 
                "[SYSTEM] TTS engine tag enabled.", 
                "[SYSTEM] TTS engine tag disabled.", 
                True
            ),
            "speak": (
                "character_speak", 
                "[SYSTEM] Character speaking enabled.", 
                "[SYSTEM] Character speaking disabled.", 
                True
            ),
            "narration": (
                "speak_narration", 
                "[SYSTEM] Narration enabled.", 
                "[SYSTEM] Narration disabled.", 
                False
            ),
            "command": (
                "execute_command", 
                "[SYSTEM] Command execution enabled.", 
                "[SYSTEM] Command execution disabled.", 
                False
            ),
            "clear": (
                "clear_on_start", 
                "[SYSTEM] Console will now clear at startup.", 
                "[SYSTEM] Console will no longer clear at startup.", 
                True
            ),
            "recap": (
                "auto_recap_on_start", 
                "[SYSTEM] Auto recap at startup is now enabled.", 
                "[SYSTEM] Auto recap at startup is now disabled.", 
                True
            ),
            "errors": (
                "suppress_errors", 
                "[SYSTEM] Non-critical error messages suppressed.", 
                "[SYSTEM] Error messages will now be shown.", 
                False
            ),
            "privacy": (
                "privacy_mode", 
                "[SYSTEM] Privacy mode enabled.", 
                "[SYSTEM] Privacy mode disabled.", 
                False
            ),
            "debug": (
                "debug_mode", 
                "[SYSTEM] Debug mode enabled.", 
                "[SYSTEM] Debug mode disabled.", 
                False
            ),
        }

        if choice in toggle_map:
            key, enabled_msg, disabled_msg, default_val = toggle_map[choice]
            current = get_setting(key, default_val)
            new_val = not current
            update_setting(key, new_val)
            
            # Special color mapping for errors: enabling suppression is RED, disabling is GREEN
            if choice == "errors":
                color = Fore.RED if new_val else Fore.GREEN
            else:
                color = Fore.GREEN if new_val else Fore.RED
                
            _log(enabled_msg if new_val else disabled_msg, color)
        else:
            _log(f"[ERROR] Unknown setting to toggle: '{choice}'. Use //toggle to list options.", Fore.RED)

    def _reset(args=None):
        """Resets chat history or relationship score. Usage: //reset [all|rel] [profile]"""
        subcommand = ""
        target_profile = ""
        
        if args and isinstance(args, str) and args.strip():
            parts = args.strip().split()
            if parts:
                subcommand = parts[0].lower()
                if len(parts) > 1:
                    target_profile = parts[1]

        # Case 1: //reset rel -> reset relationship score
        if subcommand == "rel":
            if target_profile:
                profile_path = os.path.join("profiles", target_profile if target_profile.endswith(".json") else f"{target_profile}.json")
            else:
                if suppress_output:
                    current_profile_setting = get_setting("current_character_profile")
                    if current_profile_setting:
                        profile_path = os.path.join("profiles", current_profile_setting)
                    else:
                        _log("[SYSTEM] No active character profile to reset relationship.", Fore.RED)
                        return
                else:
                    profile_path = pick_profile()
            
            if profile_path and os.path.exists(profile_path):
                from engines.utilities import save_json_atomic
                try:
                    with open(profile_path, "r", encoding="UTF-8") as f:
                        profile_data = json.load(f)
                    profile_data["relationship_score"] = 0
                    if save_json_atomic(profile_path, profile_data):
                        _log("[SYSTEM] Relationship score reset to 0.", Fore.GREEN)
                    else:
                        _log("[SYSTEM] Failed to save profile.", Fore.RED)
                except Exception as e:
                    _log(f"[ERROR] Failed to reset relationship score: {e}", Fore.RED)
            else:
                _log("[SYSTEM] No profile selected.", Fore.RED)
            return

        # Case 2: //reset all -> clear all history files
        if subcommand == "all":
            if suppress_output:
                for filename in os.listdir(HISTORY_PATH):
                    if filename.endswith(".json"):
                        profile_name = filename.replace("_history.json", "")
                        memory_manager.save_history(profile_name, [])
                _log("[SYSTEM] All history files have been wiped.", Fore.GREEN)
                return

            confirm = input(Fore.RED + "Are you sure you want to reset ALL history files? (y/n): ").strip().lower()
            if confirm == 'y':
                for filename in os.listdir(HISTORY_PATH):
                    if filename.endswith(".json"):
                        profile_name = filename.replace("_history.json", "")
                        memory_manager.save_history(profile_name, [])
                _log("[SYSTEM] All history files have been wiped.", Fore.GREEN)
            else:
                _log("[SYSTEM] Reset cancelled.", Fore.YELLOW)
            return

        # Case 3: //reset [profile_name] -> clear history of specific or active profile
        if subcommand:
            profile_name = subcommand.replace("_history.json", "").replace(".json", "")
        else:
            current_profile_setting = get_setting("current_character_profile")
            if current_profile_setting:
                profile_name = os.path.basename(current_profile_setting).replace(".json", "")
            else:
                if suppress_output:
                    _log("[SYSTEM] Manual history picking is only supported in CLI mode. Use //reset_all to clear active profile.", Fore.RED)
                    return
                else:
                    history_path = pick_history()
                    if history_path:
                        profile_name = os.path.basename(history_path).replace("_history.json", "")
                    else:
                        _log("[SYSTEM] No history selected.", Fore.RED)
                        return

        if profile_name:
            if not subcommand and not suppress_output:
                _log("[SYSTEM] Conversation history reset.", Fore.YELLOW)
            memory_manager.save_history(profile_name, [])
            _log("[SYSTEM] History cleared.", Fore.GREEN)

    def _restart():
        """Signals the main loop to restart the application."""
        _log("[SYSTEM] Restarting application...", Fore.YELLOW)
        raise RestartRequested()

    def _clear():
        """Clears the terminal screen (CLI only)."""
        if suppress_output:
            _log("[SYSTEM] Use //history to recap. TUI cannot be cleared.", Fore.YELLOW)
            return
        print("\033[H\033[J", end="")
        _log("[SYSTEM] Screen cleared.", Fore.YELLOW)

    def _change_character():
        """Changes the current character profile."""
        _log("[SYSTEM] Changing character...", Fore.YELLOW)
        raise RestartRequested()

    def _change_user_profile():
        """Changes the current user profile (CLI only)."""
        if suppress_output:
            _log("[SYSTEM] Profile switching is handled via the 'Profiles' button in TUI.", Fore.YELLOW)
            return

        _log("[SYSTEM] Changing user profile.", Fore.YELLOW)
        new_profile_path = pick_user_profile()
        if new_profile_path:
            new_profile_name = os.path.basename(new_profile_path)
            update_setting("current_user_profile", new_profile_name)
            _log(f"[SYSTEM] User profile changed to {new_profile_name}. Restarting...", Fore.GREEN)
            raise RestartRequested()
        else:
            _log("[SYSTEM] No user profile selected.", Fore.RED)

    def _history(args=None):
        """Displays the recent conversation history (CLI only)."""
        limit = 15
        if args and isinstance(args, str) and args.strip():
            try:
                limit = int(args.strip())
            except ValueError:
                pass

        if suppress_output:
            _log("[SYSTEM] History recap is already visible in TUI.", Fore.YELLOW)
            return

        current_profile_setting = get_setting("current_character_profile")
        if not current_profile_setting:
            _log("[SYSTEM] No character profile active. Cannot display history.", Fore.RED)
            return

        profile_name = os.path.basename(current_profile_setting).replace(".json", "")
        ch_name = "Assistant"
        user_name = "User"
        char_color = None

        try:
            with open(os.path.join("profiles", current_profile_setting), "r", encoding="UTF-8") as f:
                profile_data = json.load(f)
                ch_name = profile_data.get("name", "Assistant")
                colors = profile_data.get("colors", {})
                char_color = getattr(Fore, colors.get("text", "WHITE").upper(), Fore.WHITE)

            user_profile_filename = get_setting("current_user_profile")
            if user_profile_filename:
                with open(os.path.join("user_profiles", user_profile_filename), "r", encoding="UTF-8") as f:
                    user_name = json.load(f).get("name", "User")
        except:
            pass

        recap_messages = memory_manager.load_history(profile_name, limit=limit)
        if recap_messages:
            _log("\n=== Past Conversation ===", Fore.WHITE)
            for msg in recap_messages:
                render_historical_message(msg.get("role"), msg.get("content", ""), user_name=user_name, char_name=ch_name, char_color=char_color)
            _log("=========================", Fore.WHITE)
        else:
            _log("[SYSTEM] No history found for the current profile.", Fore.YELLOW)

    def _clear_cache():
        """Clears the local TTS audio cache."""
        cache_dir = "cache"
        if os.path.exists(cache_dir):
            try:
                shutil.rmtree(cache_dir)
                _log("[SYSTEM] TTS cache cleared.", Fore.GREEN)
            except Exception as e:
                _log(f"[SYSTEM] Failed to clear TTS cache: {e}", Fore.RED)
        else:
            _log("[SYSTEM] No TTS cache found to clear.", Fore.YELLOW)

    def _regen():
        """Regenerates the last AI response (TUI only)."""
        if suppress_output:
            raise RegenerateRequested()
        else:
            _log("[SYSTEM] Regeneration is only supported in TUI mode.", Fore.RED)

    def _compress():
        """Manually triggers summarization/compression of conversation history."""
        if suppress_output:
            raise CompressRequested()
        else:
            _log("[SYSTEM] Compression is only supported in TUI mode.", Fore.RED)

    def _settings():
        """Opens the TUI settings screen (TUI only)."""
        if suppress_output:
            raise SettingsRequested()
        else:
            _log("[SYSTEM] Settings GUI is only supported in TUI mode. Use //show_settings to print settings.", Fore.YELLOW)

    def _rewind(args):
        """Rewinds conversation to a specific message number. Usage: //rewind <message_number>"""
        if not args or not args.strip():
            _log("[ERROR] Usage: //rewind <message_number>", Fore.RED)
            return

        raw_value = args.strip()
        try:
            message_number = int(raw_value)
        except ValueError:
            _log(f"[ERROR] Invalid message number: {raw_value}", Fore.RED)
            return

        if message_number < 1:
            _log("[ERROR] Message number must be 1 or greater.", Fore.RED)
            return

        current_profile_setting = get_setting("current_character_profile")
        if not current_profile_setting:
            _log("[SYSTEM] No character profile active. Cannot rewind history.", Fore.RED)
            return

        profile_name = os.path.basename(current_profile_setting).replace(".json", "")
        full_data = memory_manager.get_full_data(profile_name)
        history = full_data.get("history", [])

        if not history:
            _log("[SYSTEM] No history found for the current profile.", Fore.YELLOW)
            return

        if message_number > len(history):
            _log(f"[ERROR] Message number out of range. Current history has {len(history)} messages.", Fore.RED)
            return

        if suppress_output:
            raise RewindRequested(message_number)

        original_count, kept_count = memory_manager.rewind_history(profile_name, message_number)
        _log(f"[SYSTEM] Rewound conversation from {original_count} to {kept_count} messages.", Fore.GREEN)

    def _import_card(args):
        """Imports a character card (PNG or JSON) from SillyTavern format."""
        if not args:
            _log("[ERROR] Usage: //import_card <path_to_card_png_or_json>", Fore.RED)
            return
        
        path = args.strip().strip('"').strip("'")
        if not os.path.exists(path):
            _log(f"[ERROR] File not found: {path}", Fore.RED)
            return
            
        import_character(path)
        _log(f"[SYSTEM] Successfully imported character card: {os.path.basename(path)}", Fore.GREEN)

    def _lore(args):
        """Manages the Lorebook (World Info). Usage: //lore [reload|add]"""
        if not args:
            _log("[ERROR] Usage: //lore [reload|add]", Fore.RED)
            return
        
        parts = args.strip().split(" ", 1)
        subcommand = parts[0].lower()
        sub_args = parts[1] if len(parts) > 1 else ""

        # Detect the active character's lorebook
        from engines.config import get_setting
        char_profile_setting = get_setting("current_character_profile")
        lore_path = "lorebooks/default.json" # Default fallback
        
        if char_profile_setting:
            try:
                with open(os.path.join("profiles", char_profile_setting), "r", encoding="UTF-8") as f:
                    p_data = json.load(f)
                    lore_path = p_data.get("lorebook_path") or lore_path
            except Exception:
                pass

        if subcommand == "reload":
            # Since load_lorebook is called per-turn, reload just confirms existence
            if os.path.exists(lore_path):
                _log(f"[SYSTEM] Lorebook ({os.path.basename(lore_path)}) reloaded successfully.", Fore.GREEN)
            else:
                _log(f"[SYSTEM] {os.path.basename(lore_path)} not found, but system is ready.", Fore.YELLOW)
        elif subcommand == "add":
            if "|" not in sub_args:
                _log("[ERROR] Usage: //lore add keys | content", Fore.RED)
                return
            
            keys_str, content = sub_args.split("|", 1)
            keys = [k.strip() for k in keys_str.split(",") if k.strip()]

            if not keys:
                _log("[ERROR] No valid keys provided. Usage: //lore add keys | content", Fore.RED)
                return

            os.makedirs(os.path.dirname(lore_path), exist_ok=True) if os.path.dirname(lore_path) else None
            
            from engines.lorebook import load_lorebook
            lore_data = load_lorebook(lore_path)
            
            new_entry = {
                "id": str(len(lore_data.get("entries", [])) + 1),
                "keys": keys,
                "content": content.strip(),
                "enabled": True,
                "insertion_order": 100
            }
            
            lore_data.setdefault("entries", []).append(new_entry)
            
            with open(lore_path, "w", encoding="UTF-8") as f:
                json.dump(lore_data, f, indent=4)
            
            _log(f"[SYSTEM] Added lore entry to {os.path.basename(lore_path)} for: {', '.join(keys)}", Fore.GREEN)
        else:
            _log(f"[ERROR] Unknown lore command: {subcommand}", Fore.RED)


    # Mapping of command strings to their respective functions
    cmds = {
        "//mode": lambda: _toggle("mode"),
        "//exit": _exit,
        "//quit": _exit,
        "//help": _help,
        "//clear": _clear,
        "//import_card": _import_card,
        "//lore": _lore,
        "//change_character": _change_character,
        "//change_user_profile": _change_user_profile,
        "//reset": _reset,
        "//reset_all": lambda: _reset("all"),
        "//reset_rel": lambda: _reset("rel"),
        "//restart": _restart,
        "//toggle_tts_tag": lambda: _toggle("tts_tag"),
        "//toggle_tts": lambda: _toggle("tts"),
        "//toggle_speak": lambda: _toggle("speak"),
        "//toggle_narration": lambda: _toggle("narration"),
        "//toggle_command": lambda: _toggle("command"),
        "//toggle_clear_on_start": lambda: _toggle("clear"),
        "//toggle_recap_on_start": lambda: _toggle("recap"),
        "//toggle_errors": lambda: _toggle("errors"),
        "//toggle": _toggle,
        "//show_settings": _show_settings,
        "//history": _history,
        "//recap": _history,
        "//clear_cache": _clear_cache,
        "//regen": _regen,
        "//regenerate": _regen,
        "//rewind": _rewind,
        "//compress": _compress,
        "//settings": _settings,
    }

    pattern = re.match(r'^/+', ops.strip().lower())
    if pattern:
        ops = "//" + ops[pattern.end():]
    
    # Split command and arguments
    parts = ops.split(" ", 1)
    cmd_name = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    action = cmds.get(cmd_name)
    if action:
        # Check if the function takes arguments
        import inspect
        sig = inspect.signature(action)
        try:
            if len(sig.parameters) > 0:
                action(args)
            else:
                action()
            
            if suppress_output:
                return True, output_buffer
            return True
        except RestartRequested:
            raise
        except RegenerateRequested:
            if suppress_output:
                raise
            _log("[SYSTEM] Regeneration is only supported in TUI mode.", Fore.RED)
            return True
        except CompressRequested:
            if suppress_output:
                raise
            _log("[SYSTEM] Compression is only supported in TUI mode.", Fore.RED)
            return True
        except RewindRequested:
            if suppress_output:
                raise
            _log("[SYSTEM] Rewind is only supported in TUI mode.", Fore.RED)
            return True
        except SettingsRequested:
            if suppress_output:
                raise
            _log("[SYSTEM] Settings screen is only supported in TUI mode.", Fore.RED)
            return True
        except Exception as e:
            _log(f"[ERROR] Command failed: {e}", Fore.RED)
            if suppress_output:
                return True, output_buffer
            return True

    if suppress_output:
        return False, []
    return False
