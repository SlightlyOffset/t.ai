"""
Helper utilities for terminal UI and file selection.
Provides selection menus for profiles and history files.
"""

import os
import re
import wave
import json
from colorama import Fore, Style
from engines.actions import APPS

def save_json_atomic(file_path, data, indent=4):
    """
    Saves a dictionary to a JSON file atomically to prevent corruption.
    
    Args:
        file_path (str): The destination file path.
        data (dict): The data to save.
        indent (int): JSON indentation level.
        
    Returns:
        bool: True if successful, False otherwise.
    """
    temp_file = file_path + ".tmp"
    try:
        # 1. Serialize to string first to catch TypeErrors (non-serializable objects)
        # before we even touch the file system.
        json_data = json.dumps(data, indent=indent, ensure_ascii=False)
        
        # 2. Write to a temporary file.
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(json_data)
        
        # 3. Atomic rename (overwrites existing file).
        os.replace(temp_file, file_path)
        return True
    except (TypeError, IOError, OSError):
        if os.path.exists(temp_file):
            try:
                os.remove(temp_file)
            except OSError:
                pass
        return False

def save_pcm_as_wav(pcm_data, filename, sample_rate=24000, channels=1, sample_width=2):
    """Wraps raw PCM data in a WAV header and saves to disk."""
    with wave.open(filename, 'wb') as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)

def is_command(user_input: str) -> bool:
    """
    Checks if the user input contains keywords that suggest a system command request.

    Args:
        user_input (str): The raw user input.

    Returns:
        bool: True if it looks like a command, False otherwise.
    """
    user_input = user_input.lower()
    return any(trigger in user_input for trigger in APPS.keys()) or "open" in user_input

def pick_profile() -> str:
    """
    Displays a terminal-based menu for picking a character profile.

    Returns:
        str: The path to the selected .json profile, or None.
    """
    profiles_dir = "profiles"
    if not os.path.exists(profiles_dir):
        print(Fore.RED + f"[ERROR] Profiles directory '{profiles_dir}' not found.")
        return None

    profiles = [f for f in os.listdir(profiles_dir) if f.endswith(".json")]
    if not profiles:
        print(Fore.RED + f"[ERROR] No .json profiles found in '{profiles_dir}'.")
        return None

    print(Fore.YELLOW + Style.BRIGHT + "\n--- Select Your Companion Profile ---")
    for i, p in enumerate(profiles, 1):
        display_name = p.replace(".json", "").replace("_", " ").title()
        print(Fore.CYAN + f"  [{i}] {display_name}")

    while True:
        try:
            choice = input(Fore.YELLOW + "\nEnter profile number: " + Style.RESET_ALL).strip()
            if not choice: continue
            idx = int(choice) - 1
            if 0 <= idx < len(profiles):
                selected = os.path.join(profiles_dir, profiles[idx])
                print(Fore.GREEN + f"Loading {profiles[idx]}...\n")
                return selected
            else:
                print(Fore.RED + "Invalid selection.")
        except ValueError:
            print(Fore.RED + "Please enter a valid number.")
        except KeyboardInterrupt:
            return None

def pick_user_profile() -> str:
    """
    Displays a terminal-based menu for picking a user profile.

    Returns:
        str: The path to the selected user .json profile, or None.
    """
    user_profiles_dir = "user_profiles"
    if not os.path.exists(user_profiles_dir):
        return None

    user_profiles = [f for f in os.listdir(user_profiles_dir) if f.endswith(".json")]
    if not user_profiles:
        return None

    print(Fore.YELLOW + Style.BRIGHT + "\n--- Select Your User Profile ---")
    for i, p in enumerate(user_profiles, 1):
        display_name = p.replace(".json", "").replace("_", " ").title()
        print(Fore.CYAN + f"  [{i}] {display_name}")

    while True:
        try:
            choice = input(Fore.YELLOW + "\nEnter user profile number: " + Style.RESET_ALL).strip()
            if not choice: continue
            idx = int(choice) - 1
            if 0 <= idx < len(user_profiles):
                return os.path.join(user_profiles_dir, user_profiles[idx])
            else:
                print(Fore.RED + "Invalid selection.")
        except ValueError:
            print(Fore.RED + "Please enter a valid number.")
        except KeyboardInterrupt:
            return None

def pick_history() -> str:
    """
    Displays a terminal-based menu for picking a conversation history file.

    Returns:
        str: The path to the selected history .json file, or None.
    """
    history_dir = "history"
    if not os.path.exists(history_dir):
        return None

    history_files = [f for f in os.listdir(history_dir) if f.endswith(".json")]
    if not history_files:
        return None

    print(Fore.YELLOW + Style.BRIGHT + "\n--- Select Conversation History ---")
    for i, h in enumerate(history_files, 1):
        display_name = h.replace(".json", "").replace("_", " ").title()
        print(Fore.CYAN + f"  [{i}] {display_name}")

    while True:
        try:
            choice = input(Fore.YELLOW + "\nEnter history number: " + Style.RESET_ALL).strip()
            if not choice: continue
            idx = int(choice) - 1
            if 0 <= idx < len(history_files):
                return os.path.join(history_dir, history_files[idx])
            else:
                print(Fore.RED + "Invalid selection.")
        except ValueError:
            print(Fore.RED + "Please enter a valid number.")
        except KeyboardInterrupt:
            return None

def render_historical_message(role: str, content: str, user_name: str = "User", char_name: str = "Assistant", char_color=None):
    """
    Renders a single historical message with proper styling and color.
    char_color: a colorama Fore color string for the character's dialogue (from profile colors.text).
    """
    display_role = user_name if role == "user" else char_name

    # Use the character's profile color for assistant messages; dim grey for user lines
    base_style = (char_color if char_color is not None else Fore.LIGHTBLACK_EX) if role != "user" else Fore.LIGHTBLACK_EX
    narration_style = Fore.LIGHTBLACK_EX + Style.DIM + "\033[3m" # Italics + Dimmed

    # Start with role label
    output = f"{base_style}{display_role}: "

    # Process narration tokens (*)
    parts = content.split('*')
    for i, part in enumerate(parts):
        if i % 2 == 1:
            # Inside asterisks
            output += f"{narration_style}{part}{base_style}"
        else:
            # Outside asterisks
            output += f"{base_style}{part}"

    print(output + "\n" + Style.RESET_ALL)

def get_text_style(profile_data):
    colors = profile_data.get("colors", {})
    char_style = getattr(Fore, colors.get("text", "WHITE").upper(), Fore.WHITE) + \
                    getattr(Style, colors.get("label", "NORMAL").upper(), Style.NORMAL)
    narration_style = Fore.LIGHTBLACK_EX + Style.BRIGHT + "\033[3m"
    return char_style, narration_style

def replace_placeholders(text, user_name="User", char_name="Assistant"):
    return text.replace("{{user}}", user_name).replace("{{user_name}}", user_name).replace("{{char}}", char_name)