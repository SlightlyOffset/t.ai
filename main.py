"""
Main entry point for the AI Desktop Companion.
Handles the interaction loop, multi-threaded TTS pipeline, and UI rendering.
"""
### ---------------------------
# NOTE: will be deprecated soon!
# The main.py logic will be moved into the Menu class in ui/menu.py,
# which will handle the interaction loop and rendering using Textual.
# The current main.py will be renamed to something like legacy_main.py
# and kept for reference during the transition.
### ---------------------------

# Standard library imports
import json
import threading
import random
import queue
import re
import os
import time
import sys

# Third-party imports
from colorama import init, Fore, Style

# Local imports
from engines.actions import execute_command
from engines.utilities import is_command, pick_profile, pick_user_profile, get_text_style, replace_placeholders
from engines.app_commands import app_commands, RestartRequested
from engines.responses import get_respond_stream, apply_mood_decay
from engines.tts_module import generate_audio, play_audio, clean_text_for_tts
from engines.config import update_setting, get_setting
from engines.memory_v2 import memory_manager

# Initialize colorama
init(autoreset=False)

# Clearing the console at startup
if get_setting("clear_at_start", True):
    print("\033[H\033[J", end="")

# Global configuration path
CONFIG_PATH = "settings.json"

def load_profile(profile_path):
    """Loads a character or user profile from a JSON file."""
    with open(profile_path, "r", encoding="UTF-8") as f:
        return json.load(f)

# TTS Queues
tts_text_queue = queue.Queue()
audio_file_queue = queue.Queue()

def tts_generation_worker():
    """Worker thread that converts text to MP3. Expects (text, voice, engine, clone_ref, language) tuples."""
    while True:
        data = tts_text_queue.get()
        if data is None:
            audio_file_queue.put(None)
            break

        text, voice, engine, clone_ref, language = data
        temp_dir = os.environ.get("TEMP", "/tmp")
        temp_filename = os.path.join(temp_dir, f"tts_{time.time()}_{random.randint(1000,9999)}.mp3")

        if generate_audio(text, temp_filename, voice=voice, engine=engine, clone_ref=clone_ref, language=language):
            audio_file_queue.put(temp_filename)
        tts_text_queue.task_done()

def tts_playback_worker():
    """Worker thread to play audio files in order."""
    while True:
        filename = audio_file_queue.get()
        if filename is None:
            break
        play_audio(filename)
        audio_file_queue.task_done()

def get_smart_split_points(text):
    """
    Finds split points for TTS.
    Splits on asterisks (to switch voices) and punctuation (to keep segments short).
    """
    points = []
    in_asterisks = False
    for i in range(len(text)):
        char = text[i]
        if char == '*':
            in_asterisks = not in_asterisks
            points.append(i + 1)
            continue
        if not in_asterisks:
            if char in ".!?\n":
                if char == '.' and i + 1 < len(text) and text[i+1] == '.':
                    continue
                if char == '.' and i > 0 and text[i-1] == '.':
                    continue
                points.append(i + 1)
    return points

def startup_recap(history_profile_name, user_name, ch_name):
    recap_messages = memory_manager.load_history(history_profile_name, limit=1)
    if recap_messages:
        app_commands("//history")

def run_app():
    ### --- Character Profile Loading and Initialization ---
    character_profile_path = pick_profile()
    if not character_profile_path:
        return

    character_profile = load_profile(character_profile_path)
    ch_name = character_profile["name"] # For display
    history_profile_name = os.path.basename(character_profile_path).replace(".json", "") # For history
    update_setting("current_character_profile", os.path.basename(character_profile_path)) # Set active profile

    user_profile_path = pick_user_profile()
    if user_profile_path:
        user_profile = load_profile(user_profile_path)
        user_name = user_profile.get("name", "User")
        update_setting("current_user_profile", os.path.basename(user_profile_path))
    else:
        user_name = "User"

    print(Fore.YELLOW + Style.BRIGHT + f"--- {ch_name} Desktop Companion Loaded ---" + Style.RESET_ALL)
    print(Fore.YELLOW + "Type '//help' for a list of commands.\n" + Style.RESET_ALL)

    # Startup recap
    if get_setting("auto_recap_on_start", False):
        startup_recap(history_profile_name, user_name, ch_name)

    had_history = False
    if memory_manager.get_full_data(history_profile_name).get("history"):
        had_history = True

    ### --- End of Initialization ---
    ### If no history, show starter message and save it to history to prevent it showing again on next startup.
    if not had_history:
        char_style, narration_style = get_text_style(character_profile)

        print(Fore.WHITE + Style.DIM + "-" * 30 + Style.RESET_ALL)
        # Show starter message if no history
        starter_messages = character_profile.get("starter_messages", [])
        random.shuffle(starter_messages)
        if starter_messages:
            starter_messages[0] = replace_placeholders(starter_messages[0], user_name=user_name, char_name=ch_name)
            is_currently_narrating = False
            sys.stdout.write(Fore.MAGENTA + Style.BRIGHT + f"{ch_name}: " + Style.RESET_ALL)
            parts = re.split(r'(\*)', starter_messages[0])
            for i, part in enumerate(parts):
                if part == '*':
                    is_currently_narrating = not is_currently_narrating
                    sys.stdout.write(narration_style if is_currently_narrating else char_style)
                else:
                    sys.stdout.write((narration_style if is_currently_narrating else char_style) + part)
            sys.stdout.write("\n")
            print(Fore.WHITE + Style.DIM + "-" * 30 + Style.RESET_ALL)
            sys.stdout.flush()

        memory_manager.save_history(history_profile_name, [{"role": "assistant",
                                                            "content": starter_messages[0]}],
                                    mood_score=character_profile.get("relationship_score", 0))

    # Main interaction loop
    while True:
        try:
            with open(CONFIG_PATH, "r", encoding="UTF-8") as f:
                config = json.load(f)

            profile_data = load_profile(character_profile_path)
            char_voice = profile_data.get("preferred_edge_voice", None)
            char_engine = profile_data.get("tts_engine", "edge-tts")
            char_clone_ref = profile_data.get("voice_clone_ref", None)
            char_language = profile_data.get("tts_language", "en")

            narrator_voice = get_setting("narration_tts_voice", "en-US-AndrewNeural")
            narrator_engine = "edge-tts"

            apply_mood_decay(character_profile_path, history_profile_name)

            gen_thread = threading.Thread(target=tts_generation_worker)
            play_thread = threading.Thread(target=tts_playback_worker)
            gen_thread.daemon = True; play_thread.daemon = True
            gen_thread.start(); play_thread.start()

            user_input = input(Fore.CYAN + Style.BRIGHT + f"{user_name}: " + Style.RESET_ALL).strip()
            if not user_input:
                tts_text_queue.put(None)
                gen_thread.join(); play_thread.join()
                continue

            if re.match(r'^/+', user_input.strip().lower()):
                if app_commands(user_input):
                    tts_text_queue.put(None)
                    gen_thread.join(); play_thread.join()
                    continue
                else:
                    print(Fore.RED + "[SYSTEM] Unknown command. Type '//help' for a list of commands." + Style.RESET_ALL)
                    tts_text_queue.put(None)
                    gen_thread.join(); play_thread.join()
                    continue

            should_obey = None
            if is_command(user_input) and config.get("execute_command", False):
                rel_score = profile_data.get("relationship_score", 0)
                weights = [max(0.1, profile_data.get("good_weight", 5) + (rel_score/10)),
                           max(0.1, profile_data.get("bad_weight", 5) - (rel_score/10))]
                should_obey = (random.choices(["good", "bad"], weights=weights, k=1)[0] == "good")
                if should_obey:
                    _, message = execute_command(user_input)
                    print(Fore.GREEN + f"[SYSTEM] {message}" + Style.RESET_ALL)

            # Get text styles for terminal output
            char_style, narration_style = get_text_style(profile_data)

            show_engine = get_setting("show_tts_engine", True)
            # Note: Using False to match existing main.py logic, though other modules use True.
            is_tts_enabled = get_setting("tts_enabled", False)

            if show_engine:
                engine_tag = f"[{char_engine.upper()}] " if is_tts_enabled else "[TTS DISABLED] "
            else:
                engine_tag = ""

            print(Fore.WHITE + Style.DIM + "-" * 30 + Style.RESET_ALL)
            sys.stdout.write(Fore.CYAN + engine_tag + Fore.MAGENTA + Style.BRIGHT + f"{ch_name}: " + Style.RESET_ALL)
            sys.stdout.write(Style.DIM + "thinking..." + Style.RESET_ALL)
            sys.stdout.flush()

            full_response = ""
            current_buffer = ""
            is_currently_narrating = False # Tracks state for terminal printing
            tts_in_narration = False      # Tracks state for voice selection
            first_chunk = True

            # ------------------------------------------------
            # Switch for TTS settings
            speak_enable = get_setting("character_speak", False)
            narration_enable = get_setting("speak_narration", False)
            # ------------------------------------------------

            for chunk in get_respond_stream(user_input, profile_data, should_obey=should_obey, profile_path=character_profile_path):
                if first_chunk:
                    # Clear "thinking..." (11 chars)
                    sys.stdout.write("\b" * 11 + " " * 11 + "\b" * 11)
                    sys.stdout.flush()
                    first_chunk = False

                for char in chunk:
                    if char == '*':
                        is_currently_narrating = not is_currently_narrating
                        sys.stdout.write(narration_style if is_currently_narrating else char_style)
                        # sys.stdout.write(char) # Optionally print the asterisk if you want a visual toggle in the terminal
                    else:
                        sys.stdout.write((narration_style if is_currently_narrating else char_style) + char)
                sys.stdout.flush()

                full_response += chunk
                current_buffer += chunk

                # ---------------------------------------------------------------
                # This entire block responsible for deciding when to send text to TTS, and which voice/engine to use.
                # Check for split points
                if get_setting("tts_enabled", False):
                    split_points = get_smart_split_points(current_buffer)
                    if split_points:
                        last_point = 0
                        for point in split_points:
                            segment = current_buffer[last_point:point]

                            # Voice selection uses state at START of segment (before any toggle).
                            # Split points land after every *, so each segment has at most one *
                            # at its end — the content before it belongs to the pre-toggle voice.
                            voice = narrator_voice if tts_in_narration else char_voice
                            engine = narrator_engine if tts_in_narration else char_engine
                            clone_ref = None if tts_in_narration else char_clone_ref
                            language = "en" if tts_in_narration else char_language

                            # Toggle AFTER voice selection so routing also uses pre-toggle state
                            if '*' in segment:
                                tts_in_narration = not tts_in_narration

                            cleaned = clean_text_for_tts(segment, speak_narration=True)
                            if cleaned:
                                # Only narration enabled: send segments that were narration before toggle
                                if not speak_enable and narration_enable and (voice == narrator_voice):
                                    tts_text_queue.put((cleaned, voice, engine, clone_ref, language))
                                # Only character speech enabled: send segments that were dialogue before toggle
                                elif speak_enable and not narration_enable and (voice == char_voice):
                                    tts_text_queue.put((cleaned, voice, engine, clone_ref, language))
                                # Both enabled: send everything
                                elif speak_enable and narration_enable:
                                    tts_text_queue.put((cleaned, voice, engine, clone_ref, language))
                            last_point = point
                        current_buffer = current_buffer[last_point:]
                # ---------------------------------------------------------------

            # After the full response is printed, check if there's any leftover text that hasn't been sent to TTS yet (e.g. after the last punctuation or asterisk)
            if get_setting("tts_enabled", False) and current_buffer.strip():
                cleaned = clean_text_for_tts(current_buffer.strip(), speak_narration=True)
                if cleaned:
                    if not speak_enable and narration_enable and (voice == narrator_voice):     #type: ignore
                        tts_text_queue.put((cleaned, voice, engine, clone_ref, language))       #type: ignore
                    elif speak_enable and not narration_enable and (voice == char_voice):       #type: ignore
                        tts_text_queue.put((cleaned, voice, engine, clone_ref, language))       #type: ignore
                    elif speak_enable and narration_enable:
                        tts_text_queue.put((cleaned, voice, engine, clone_ref, language))       #type: ignore


            sys.stdout.write(Style.RESET_ALL + "\n")
            print(Fore.WHITE + Style.DIM + "-" * 30 + Style.RESET_ALL)
            sys.stdout.flush()

            tts_text_queue.put(None)
            gen_thread.join(); play_thread.join()

        except (KeyboardInterrupt, RestartRequested):
            sys.stdout.write(Style.RESET_ALL); sys.stdout.flush()
            raise
        except Exception as e:
            sys.stdout.write(Style.RESET_ALL)
            print(Fore.RED + f"\n[ERROR] {e}" + Style.RESET_ALL)

def main():
    while True:
        try:
            run_app()
        except RestartRequested:
            print("\033[H\033[J", end="")
            continue
        except KeyboardInterrupt:
            print(Style.RESET_ALL + Fore.YELLOW + "\n[SYSTEM] Shutting down..." + Style.RESET_ALL)
            break
        except Exception as e:
            print(Style.RESET_ALL + Fore.RED + f"\n[CRITICAL ERROR] {e}" + Style.RESET_ALL)
            break

if __name__ == "__main__":
    main()
