"""
Remote XTTS v2 client.
Handles communication with the Google Colab bridge for remote voice cloning.
"""

import requests
import os
import hashlib
from colorama import Fore
from engines.config import get_setting
from engines.utilities import save_pcm_as_wav

# In-memory cache to track which voices have been uploaded to the current session's bridge
_UPLOADED_VOICES = set()

def _get_speaker_id(speaker_wavs):
    """Generates a stable speaker ID based on the file paths or content."""
    if isinstance(speaker_wavs, str):
        speaker_wavs = [speaker_wavs]
    
    # Use parent directory name if consistent, otherwise hash the paths
    dirs = set(os.path.dirname(p) for p in speaker_wavs)
    if len(dirs) == 1:
        return os.path.basename(list(dirs)[0])
    
    path_string = "|".join(sorted(speaker_wavs))
    return hashlib.md5(path_string.encode()).hexdigest()[:12]

def ensure_voice_on_bridge(bridge_url, speaker_id, speaker_wavs):
    """Checks if the bridge has the speaker; uploads if missing."""
    if speaker_id in _UPLOADED_VOICES:
        return True

    try:
        # 1. Check if exists
        check_url = f"{bridge_url.rstrip('/')}/check_speaker/{speaker_id}"
        r = requests.get(check_url, timeout=5)
        if r.status_code == 200 and r.json().get("exists"):
            _UPLOADED_VOICES.add(speaker_id)
            return True

        # 2. Upload if missing
        print(Fore.CYAN + f"[XTTS REMOTE] Uploading voice profile '{speaker_id}' to bridge..." + Fore.RESET)
        upload_url = f"{bridge_url.rstrip('/')}/upload_speaker"
        
        file_handles = [open(p, "rb") for p in speaker_wavs]
        try:
            files = [("files", (os.path.basename(p), fh, "audio/wav"))
                     for p, fh in zip(speaker_wavs, file_handles)]
            data = {"speaker_id": speaker_id}
            resp = requests.post(upload_url, data=data, files=files, timeout=30)
            
            if resp.status_code == 200:
                _UPLOADED_VOICES.add(speaker_id)
                return True
            else:
                print(Fore.RED + f"[XTTS UPLOAD ERROR] {resp.status_code}: {resp.text}" + Fore.RESET)
                return False
        finally:
            for fh in file_handles:
                fh.close()
                
    except Exception as e:
        print(Fore.RED + f"[XTTS BRIDGE CONN ERROR] {e}" + Fore.RESET)
        return False

def generate_remote_xtts(text, output_path, speaker_wav, language="en"):
    """
    Sends a generation request to the remote Google Colab bridge.
    Uses speaker caching to avoid redundant uploads.
    """
    bridge_url = get_setting("remote_tts_url")
    if not bridge_url:
        if not get_setting("suppress_errors", False):
            print(Fore.RED + "[XTTS REMOTE] Error: 'remote_tts_url' not set." + Fore.RESET)
        return False

    speaker_id = _get_speaker_id(speaker_wav)
    if isinstance(speaker_wav, str):
        speaker_wav = [speaker_wav]

    # Ensure speaker is cached on the bridge
    if not ensure_voice_on_bridge(bridge_url, speaker_id, speaker_wav):
        return False

    try:
        endpoint = f"{bridge_url.rstrip('/')}/generate_tts"
        data = {
            "text": text,
            "language": language,
            "speaker_id": speaker_id
        }

        if get_setting("debug_mode", False):
            print(Fore.MAGENTA + f"[DEBUG] Requesting remote XTTS for speaker: {speaker_id}" + Fore.RESET)

        # For now, we still download the full file, but without the 'files' payload.
        # Phase 2 will implement real-time streaming playback.
        response = requests.post(endpoint, data=data, timeout=60, stream=True)

        if response.status_code == 200:
            all_pcm = b""
            for chunk in response.iter_content(chunk_size=4096):
                all_pcm += chunk
            
            # Wrap the collected PCM in a WAV header and save
            save_pcm_as_wav(all_pcm, output_path)
            return True
        else:
            if not get_setting("suppress_errors", False):
                print(Fore.RED + f"[XTTS REMOTE ERROR] {response.status_code}" + Fore.RESET)
            return False

    except Exception as e:
        if not get_setting("suppress_errors", False):
            print(Fore.RED + f"[XTTS REMOTE ERROR] {e}" + Fore.RESET)
        return False
