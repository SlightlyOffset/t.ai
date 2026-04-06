"""
Internal CLI command handler for the application.
Processes commands starting with '//' to manage settings, history, and app state.
"""
import sys
import os
import shutil
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import re
import json
from colorama import Fore, init, Style
from engines.config import update_setting, get_setting
from engines.utilities import pick_history
from engines.utilities import pick_profile
from engines.utilities import pick_user_profile, render_historical_message # Import render_historical_message
from engines.memory_v2 import memory_manager # Import memory_manager
from engines.character_importer import import_character

# Initialize colorama
init(autoreset=True)


# Path to conversation history files
HISTORY_PATH = "history/"

class RestartRequested(Exception):
    """Exception raised to signal the main loop to restart the application."""
    pass

def app_commands(ops: str):
    """
    Dispatcher for internal operational commands.

    Args:
        ops (str): The raw command input (e.g., '//help').

    Returns:
        bool: True if the command was recognized and handled, False otherwise.
    """

    def _help():
        """Lists all available commands."""
        print(Fore.YELLOW + "[AVAILABLE COMMANDS]")
        for cmd, func in cmds.items():
            doc = func.__doc__ if func.__doc__ else ""
            # Simple parsing for help text
            desc = doc.split("\n")[0] if doc else ""
            print(Fore.CYAN + f"  {cmd:<25}" + Fore.WHITE + f" - {desc}")

    def _exit():
        """Exits the application."""
        print(Fore.YELLOW + "[SYSTEM] Exiting application...")
        sys.exit(0)

    def _show_settings():
        """Displays current system settings from settings.json."""
        from engines.config import load_settings
        settings = load_settings()
        print(Fore.YELLOW + "[CURRENT SETTINGS]")
        for key, value in settings.items():
            # Color-code booleans for readability
            val_str = Fore.GREEN + str(value) if isinstance(value, bool) and value else \
                      Fore.RED + str(value) if isinstance(value, bool) else \
                      Fore.WHITE + str(value)
            print(Fore.CYAN + f"  {key}: " + val_str)

    def _toggle_tts():
        """Toggles Text-to-Speech on or off."""
        is_enabled = get_setting("tts_enabled", True)
        print(Fore.GREEN + "[SYSTEM] Text-to-Speech enabled." if not is_enabled else Fore.RED + "[SYSTEM] Text-to-Speech disabled.")
        update_setting("tts_enabled", not is_enabled)

    def _toggle_tts_tag():
        """Toggles the visibility of the TTS engine tag in chat."""
        is_enabled = get_setting("show_tts_engine", True)
        print(Fore.GREEN + "[SYSTEM] TTS engine tag enabled." if not is_enabled else Fore.RED + "[SYSTEM] TTS engine tag disabled.")
        update_setting("show_tts_engine", not is_enabled)

    def _toggle_narration():
        """Toggles whether narration (text in asterisks) is spoken."""
        is_enabled = get_setting("speak_narration", False)
        print(Fore.GREEN + "[SYSTEM] Narration enabled." if not is_enabled else Fore.RED + "[SYSTEM] Narration disabled.")
        update_setting("speak_narration", not is_enabled)

    def _toggle_speak():
        """Toggles whether character dialogue is spoken."""
        is_enabled = get_setting("character_speak", True)
        print(Fore.GREEN + "[SYSTEM] Character speaking enabled." if not is_enabled else Fore.RED + "[SYSTEM] Character speaking disabled.")
        update_setting("character_speak", not is_enabled)

    def _toggle_command():
        """Toggles the AI's ability to execute system commands."""
        is_enabled = get_setting("execute_command", False)
        print(Fore.GREEN + "[SYSTEM] Command execution enabled." if not is_enabled else Fore.RED + "[SYSTEM] Command execution disabled.")
        update_setting("execute_command", not is_enabled)

    def _reset():
        """Wipes a specific history file chosen by the user."""
        print(Fore.YELLOW + "[SYSTEM] Conversation history reset.")
        history_path = pick_history()
        if history_path:
            # Extract profile name from filename (e.g., 'Glitch_history.json' -> 'Glitch')
            profile_name = os.path.basename(history_path).replace("_history.json", "")
            memory_manager.save_history(profile_name, [])
            print(Fore.GREEN + "[SYSTEM] History cleared.")

            # Reprint starter message if a profile is currently active
        else:
            print(Fore.RED + "[SYSTEM] No history selected.")

    def _reset_all():
        """Wipes ALL history files in the history directory."""
        confirm = input(Fore.RED + "Are you sure you want to reset ALL history files? (y/n): ").strip().lower()
        if confirm == 'y':
            from engines.memory_v2 import memory_manager
            for filename in os.listdir(HISTORY_PATH):
                if filename.endswith(".json"):
                    profile_name = filename.replace("_history.json", "")
                    memory_manager.save_history(profile_name, [])
            print(Fore.GREEN + "[SYSTEM] All history files have been wiped.")
        else:
            print(Fore.YELLOW + "[SYSTEM] Reset cancelled.")

    def _reset_rel():
        """Resets the relationship score of a chosen profile to zero."""
        profile_path = pick_profile()
        if profile_path:
            with open(profile_path, "r+", encoding="UTF-8") as f:
                profile_data = json.load(f)
                profile_data["relationship_score"] = 0
                f.seek(0)
                json.dump(profile_data, f, indent=4)
                f.truncate()
            print(Fore.GREEN + "[SYSTEM] Relationship score reset to 0.")
        else:
            print(Fore.RED + "[SYSTEM] No profile selected.")

    # Note: Still somewhat buggy.
    def _restart():
        """Signals the main loop to restart the application."""
        print(Fore.YELLOW + "[SYSTEM] Restarting application...")
        raise RestartRequested()

    def _clear():
        """Clears the terminal screen."""
        print("\033[H\033[J", end="")
        print(Fore.YELLOW + "[SYSTEM] Screen cleared.")

    def _change_character():
        """Changes the current character profile."""
        print(Fore.YELLOW + "[SYSTEM] Changing character...")
        raise RestartRequested()

    def _change_user_profile():
        """Changes the current user profile."""
        print(Fore.YELLOW + "[SYSTEM] Changing user profile.")
        new_profile_path = pick_user_profile()
        if new_profile_path:
            new_profile_name = os.path.basename(new_profile_path)
            update_setting("current_user_profile", new_profile_name)
            print(Fore.GREEN + f"[SYSTEM] User profile changed to {new_profile_name}. Restarting...")
            raise RestartRequested()
        else:
            print(Fore.RED + "[SYSTEM] No user profile selected.")

    def _toggle_clear_on_start():
        """Toggles whether the console clears on application start."""
        is_enabled = get_setting("clear_at_start", True)
        print(Fore.GREEN + "[SYSTEM] Console will now clear at startup." if not is_enabled else Fore.RED + "[SYSTEM] Console will no longer clear at startup.")
        update_setting("clear_at_start", not is_enabled)

    def _toggle_errors():
        """Toggles the suppression of non-critical error messages."""
        is_enabled = get_setting("suppress_errors", False)
        print(Fore.GREEN + "[SYSTEM] Error messages will now be shown." if is_enabled else Fore.RED + "[SYSTEM] Non-critical error messages suppressed.")
        update_setting("suppress_errors", not is_enabled)

    def _history(limit: int = 15):
        """Displays the recent conversation history."""
        current_profile_setting = get_setting("current_character_profile")
        if not current_profile_setting:
            print(Fore.RED + "[SYSTEM] No character profile active. Cannot display history." + Style.RESET_ALL)
            return

        # Extract character name from the profile path stored in settings
        profile_name = os.path.basename(current_profile_setting).replace(".json", "")

        # Try to get display names
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
            print(Fore.WHITE + Style.DIM + "\n=== Past Conversation ===" + Style.RESET_ALL)
            for msg in recap_messages:
                render_historical_message(msg.get("role"), msg.get("content", ""), user_name=user_name, char_name=ch_name, char_color=char_color)
            print(Fore.WHITE + Style.DIM + "=========================" + Style.RESET_ALL)
        else:
            print(Fore.YELLOW + "[SYSTEM] No history found for the current profile." + Style.RESET_ALL)

    def _toggle_recap_on_start():
        """Toggles whether a history recap is shown at startup."""
        is_enabled = get_setting("auto_recap_on_start", True)
        print(Fore.GREEN + "[SYSTEM] Auto recap at startup is now enabled." if not is_enabled else Fore.RED + "[SYSTEM] Auto recap at startup is now disabled.")
        update_setting("auto_recap_on_start", not is_enabled)

    def _clear_cache():
        """Clears the local TTS audio cache."""
        cache_dir = "cache"
        if os.path.exists(cache_dir):
            try:
                shutil.rmtree(cache_dir)
                print(Fore.GREEN + "[SYSTEM] TTS cache cleared.")
            except Exception as e:
                print(Fore.RED + f"[SYSTEM] Failed to clear TTS cache: {e}")
        else:
            print(Fore.YELLOW + "[SYSTEM] No TTS cache found to clear.")

    def _toggle_mode():
        """Toggles between Roleplay (RP) and Casual interaction modes."""
        current_mode = get_setting("interaction_mode", "rp")
        new_mode = "casual" if current_mode == "rp" else "rp"
        update_setting("interaction_mode", new_mode)
        print(Fore.GREEN + f"[SYSTEM] Interaction mode set to {new_mode.upper()}.")

    def _import_card(args):
        """Imports a character card (PNG or JSON) from SillyTavern format."""
        if not args:
            print(Fore.RED + "[ERROR] Usage: //import_card <path_to_card_png_or_json>")
            return
        
        path = args.strip().strip('"').strip("'")
        if not os.path.exists(path):
            print(Fore.RED + f"[ERROR] File not found: {path}")
            return
            
        import_character(path)

    # Mapping of command strings to their respective functions
    cmds = {
        "//mode": _toggle_mode,
        "//exit": _exit,
        "//quit": _exit,
        "//help": _help,
        "//clear": _clear,
        "//import_card": _import_card,
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
        "//toggle_clear_at_start": _toggle_clear_on_start,
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
        if len(sig.parameters) > 0:
            action(args)
        else:
            action()
        return True
    return False
