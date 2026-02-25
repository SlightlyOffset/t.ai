"""
Remote XTTS v2 client.
Handles communication with the Google Colab bridge for remote voice cloning.
"""

import requests
import os
from colorama import Fore
from engines.config import get_setting

def generate_remote_xtts(text, output_path, speaker_wav, language="en"):
    """
    Sends a generation request to the remote Google Colab bridge.
    speaker_wav can be a single path string or a list of paths for multi-sample cloning.
    """
    bridge_url = get_setting("remote_tts_url")
    if not bridge_url:
        if not get_setting("suppress_errors", False):
            print(Fore.RED + "[XTTS REMOTE] Error: 'remote_tts_url' not set in settings.json." + Fore.RESET)
        return False

    # Normalize to list
    if isinstance(speaker_wav, str):
        speaker_wav = [speaker_wav]

    for path in speaker_wav:
        if not os.path.exists(path):
            if not get_setting("suppress_errors", False):
                print(Fore.RED + f"[XTTS REMOTE] Error: Speaker reference '{path}' not found." + Fore.RESET)
            return False

    try:
        endpoint = f"{bridge_url.rstrip('/')}/generate_tts"

        file_handles = [open(p, "rb") for p in speaker_wav]
        try:
            files = [("speaker_files", (os.path.basename(p), fh, "audio/wav"))
                     for p, fh in zip(speaker_wav, file_handles)]
            data = {"text": text, "language": language}

            if get_setting("debug_mode", False):
                print(Fore.MAGENTA + f"[DEBUG] Sending text to XTTS: {text}" + Fore.RESET)
                print(Fore.CYAN + "[XTTS REMOTE] Requesting audio from Colab bridge..." + Fore.RESET)
            response = requests.post(endpoint, data=data, files=files, timeout=60)
        finally:
            for fh in file_handles:
                fh.close()

        if response.status_code == 200:
            with open(output_path, "wb") as out:
                out.write(response.content)
            return True
        else:
            if not get_setting("suppress_errors", False):
                print(Fore.RED + f"[XTTS REMOTE ERROR] Server returned {response.status_code}: {response.text}" + Fore.RESET)
            return False

    except Exception as e:
        if not get_setting("suppress_errors", False):
            print(Fore.RED + f"[XTTS REMOTE ERROR] Failed to connect to bridge: {e}" + Fore.RESET)
        return False
