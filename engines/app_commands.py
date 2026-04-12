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
from colorama import Fore, init, Style

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

class RestartRequested(Exception):
    """Exception raised to signal the main loop to restart the application."""
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
            _log(f"  {key}: {value}", Fore.CYAN)

    def _toggle_tts():
        """Toggles Text-to-Speech on or off."""
        is_enabled = get_setting("tts_enabled", True)
        _log("[SYSTEM] Text-to-Speech enabled." if not is_enabled else "[SYSTEM] Text-to-Speech disabled.", 
             Fore.GREEN if not is_enabled else Fore.RED)
        update_setting("tts_enabled", not is_enabled)

    def _toggle_tts_tag():
        """Toggles the visibility of the TTS engine tag in chat."""
        is_enabled = get_setting("show_tts_engine", True)
        _log("[SYSTEM] TTS engine tag enabled." if not is_enabled else "[SYSTEM] TTS engine tag disabled.",
             Fore.GREEN if not is_enabled else Fore.RED)
        update_setting("show_tts_engine", not is_enabled)

    def _toggle_narration():
        """Toggles whether narration (text in asterisks) is spoken."""
        is_enabled = get_setting("speak_narration", False)
        _log("[SYSTEM] Narration enabled." if not is_enabled else "[SYSTEM] Narration disabled.",
             Fore.GREEN if not is_enabled else Fore.RED)
        update_setting("speak_narration", not is_enabled)

    def _toggle_speak():
        """Toggles whether character dialogue is spoken."""
        is_enabled = get_setting("character_speak", True)
        _log("[SYSTEM] Character speaking enabled." if not is_enabled else "[SYSTEM] Character speaking disabled.",
             Fore.GREEN if not is_enabled else Fore.RED)
        update_setting("character_speak", not is_enabled)

    def _toggle_command():
        """Toggles the AI's ability to execute system commands."""
        is_enabled = get_setting("execute_command", False)
        _log("[SYSTEM] Command execution enabled." if not is_enabled else "[SYSTEM] Command execution disabled.",
             Fore.GREEN if not is_enabled else Fore.RED)
        update_setting("execute_command", not is_enabled)

    def _reset():
        """Wipes a specific history file (only works in CLI)."""
        if suppress_output:
            _log("[SYSTEM] Manual history picking is only supported in CLI mode. Use //reset_all to clear active profile.", Fore.RED)
            return

        _log("[SYSTEM] Conversation history reset.", Fore.YELLOW)
        history_path = pick_history()
        if history_path:
            profile_name = os.path.basename(history_path).replace("_history.json", "")
            memory_manager.save_history(profile_name, [])
            _log("[SYSTEM] History cleared.", Fore.GREEN)
        else:
            _log("[SYSTEM] No history selected.", Fore.RED)

    def _reset_all():
        """Wipes ALL history files in the history directory."""
        if suppress_output:
            # In TUI, we don't want interactive prompts here. 
            # We'll just assume they want to clear everything or we could make a specific TUI command.
            from engines.memory_v2 import memory_manager
            for filename in os.listdir(HISTORY_PATH):
                if filename.endswith(".json"):
                    profile_name = filename.replace("_history.json", "")
                    memory_manager.save_history(profile_name, [])
            _log("[SYSTEM] All history files have been wiped.", Fore.GREEN)
            return

        confirm = input(Fore.RED + "Are you sure you want to reset ALL history files? (y/n): ").strip().lower()
        if confirm == 'y':
            from engines.memory_v2 import memory_manager
            for filename in os.listdir(HISTORY_PATH):
                if filename.endswith(".json"):
                    profile_name = filename.replace("_history.json", "")
                    memory_manager.save_history(profile_name, [])
            _log("[SYSTEM] All history files have been wiped.", Fore.GREEN)
        else:
            _log("[SYSTEM] Reset cancelled.", Fore.YELLOW)

    def _reset_rel():
        """Resets the relationship score of a chosen profile to zero (CLI only)."""
        if suppress_output:
             _log("[SYSTEM] Manual relationship reset is only supported in CLI mode.", Fore.RED)
             return

        from engines.utilities import pick_profile, save_json_atomic
        profile_path = pick_profile()
        if profile_path:
            with open(profile_path, "r", encoding="UTF-8") as f:
                profile_data = json.load(f)
            
            profile_data["relationship_score"] = 0
            if save_json_atomic(profile_path, profile_data):
                _log("[SYSTEM] Relationship score reset to 0.", Fore.GREEN)
            else:
                _log("[SYSTEM] Failed to save profile.", Fore.RED)
        else:
            _log("[SYSTEM] No profile selected.", Fore.RED)

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

    def _toggle_clear_on_start():
        """Toggles whether the console clears on application start."""
        is_enabled = get_setting("clear_on_start", True)
        _log("[SYSTEM] Console will now clear at startup." if not is_enabled else "[SYSTEM] Console will no longer clear at startup.",
             Fore.GREEN if not is_enabled else Fore.RED)
        update_setting("clear_on_start", not is_enabled)

    def _toggle_errors():
        """Toggles the suppression of non-critical error messages."""
        is_enabled = get_setting("suppress_errors", False)
        _log("[SYSTEM] Error messages will now be shown." if is_enabled else "[SYSTEM] Non-critical error messages suppressed.",
             Fore.GREEN if is_enabled else Fore.RED)
        update_setting("suppress_errors", not is_enabled)

    def _history(limit: int = 15):
        """Displays the recent conversation history (CLI only)."""
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

    def _toggle_recap_on_start():
        """Toggles whether a history recap is shown at startup."""
        is_enabled = get_setting("auto_recap_on_start", True)
        _log("[SYSTEM] Auto recap at startup is now enabled." if not is_enabled else "[SYSTEM] Auto recap at startup is now disabled.",
             Fore.GREEN if not is_enabled else Fore.RED)
        update_setting("auto_recap_on_start", not is_enabled)

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

    def _toggle_mode():
        """Toggles between Roleplay (RP) and Casual interaction modes."""
        current_mode = get_setting("interaction_mode", "rp")
        new_mode = "casual" if current_mode == "rp" else "rp"
        update_setting("interaction_mode", new_mode)
        _log(f"[SYSTEM] Interaction mode set to {new_mode.upper()}.", Fore.GREEN)

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

        if subcommand == "reload":
            # Since load_lorebook is called per-turn, reload just confirms existence
            lore_path = "lorebooks/default.json"
            if os.path.exists(lore_path):
                _log("[SYSTEM] Lorebook reloaded successfully.", Fore.GREEN)
            else:
                _log("[SYSTEM] Lorebook file not found, but system is ready.", Fore.YELLOW)
        elif subcommand == "add":
            if "|" not in sub_args:
                _log("[ERROR] Usage: //lore add keys | content", Fore.RED)
                return
            
            keys_str, content = sub_args.split("|", 1)
            keys = [k.strip() for k in keys_str.split(",")]
            
            # Detect the active character's lorebook
            from engines.config import get_setting
            char_profile_setting = get_setting("current_character_profile")
            lore_path = "lorebooks/default.json" # Default fallback
            
            if char_profile_setting:
                try:
                    with open(os.path.join("profiles", char_profile_setting), "r", encoding="UTF-8") as f:
                        p_data = json.load(f)
                        lore_path = p_data.get("lorebook_path", lore_path)
                except Exception:
                    pass

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
        "//mode": _toggle_mode,
        "//exit": _exit,
        "//quit": _exit,
        "//help": _help,
        "//clear": _clear,
        "//import_card": _import_card,
        "//lore": _lore,
        "//change_character": _change_character,
        "//change_user_profile": _change_user_profile,
        "//reset": _reset,
        "//reset_all": _reset_all,
        "//reset_rel": _reset_rel,
        "//restart": _restart,
        '//toggle_tts_tag': _toggle_tts_tag,
        "//toggle_tts": _toggle_tts,
        "//toggle_speak": _toggle_speak,
        "//toggle_narration": _toggle_narration,
        "//toggle_command": _toggle_command,
        "//toggle_clear_on_start": _toggle_clear_on_start,
        "//toggle_recap_on_start": _toggle_recap_on_start,
        "//toggle_errors": _toggle_errors,
        "//show_settings": _show_settings,
        "//history": _history,
        "//recap": _history,
        "//clear_cache": _clear_cache,
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
        except Exception as e:
            _log(f"[ERROR] Command failed: {e}", Fore.RED)
            if suppress_output:
                return True, output_buffer
            return True

    if suppress_output:
        return False, []
    return False
