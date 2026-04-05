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

    # Common headers for ngrok-based bridges to bypass warning pages
    # Connection: close can help with 10054 resets on some proxies
    headers = {
        "ngrok-skip-browser-warning": "true",
        "Connection": "close"
    }

    try:
        # 1. Pre-flight Check: Ensure bridge is reachable at all
        try:
            r_ping = requests.get(bridge_url.rstrip('/'), headers=headers, timeout=5)
            if r_ping.status_code >= 500:
                print(Fore.YELLOW + f"[XTTS REMOTE] Warning: Bridge returned {r_ping.status_code}. It might still be starting up." + Fore.RESET)
        except Exception as e:
            print(Fore.RED + f"[XTTS BRIDGE CONN ERROR] Cannot reach bridge at {bridge_url}. Is it running? ({e})" + Fore.RESET)
            return False

        # 2. Check if speaker exists
        check_url = f"{bridge_url.rstrip('/')}/check_speaker/{speaker_id}"
        if get_setting("debug_mode", False):
            print(Fore.MAGENTA + f"[DEBUG] Checking speaker existence: {check_url}" + Fore.RESET)
            
        r = requests.get(check_url, headers=headers, timeout=10)
        
        if r.status_code == 200:
            try:
                data = r.json()
                if data.get("exists"):
                    _UPLOADED_VOICES.add(speaker_id)
                    return True
            except ValueError:
                pass 

        # 3. Upload if missing
        print(Fore.CYAN + f"[XTTS REMOTE] Uploading voice profile '{speaker_id}' to bridge..." + Fore.RESET)
        upload_url = f"{bridge_url.rstrip('/')}/upload_speaker"

        if not speaker_wavs:
            print(Fore.RED + f"[XTTS UPLOAD ERROR] No wav files found for speaker '{speaker_id}'" + Fore.RESET)
            return False

        # STRICT LIMIT: Only upload the SINGLE largest/most-representative sample.
        # This minimizes the POST body size to ~1-2MB, which is the most stable range
        # for Colab/Ngrok during peak hours.
        candidates = speaker_wavs[:3]
        best_sample = max(candidates, key=os.path.getsize)
        upload_samples = [best_sample]

        if get_setting("debug_mode", False):
            print(Fore.MAGENTA + f"[DEBUG] Using best single sample: {os.path.basename(best_sample)} ({os.path.getsize(best_sample)} bytes)" + Fore.RESET)

        file_handles = [open(p, "rb") for p in upload_samples]
        try:
            files = [("files", (os.path.basename(p), fh, "audio/wav"))
                     for p, fh in zip(upload_samples, file_handles)]
            data = {"speaker_id": speaker_id}
            
            # Additional headers to look more like a standard browser request
            headers.update({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "*/*"
            })
            
            # Use a conservative 60s timeout for the single-file POST
            resp = requests.post(upload_url, data=data, files=files, headers=headers, timeout=60)

            if resp.status_code == 200:
                print(Fore.GREEN + f"[XTTS REMOTE] Voice profile '{speaker_id}' registered successfully." + Fore.RESET)
                _UPLOADED_VOICES.add(speaker_id)
                return True
            else:
                print(Fore.RED + f"[XTTS UPLOAD ERROR] {resp.status_code}: {resp.text}" + Fore.RESET)
                return False
        finally:
            for fh in file_handles:
                fh.close()

    except requests.exceptions.ConnectionError as ce:
        print(Fore.RED + f"[XTTS BRIDGE CONN ERROR] Connection failed: {ce}" + Fore.RESET)
        if "10054" in str(ce):
            print(Fore.YELLOW + "[TIP] Error 10054 detected. Trying again with fewer samples. If this persists, restart your Colab notebook." + Fore.RESET)
        return False
    except Exception as e:
        print(Fore.RED + f"[XTTS BRIDGE CONN ERROR] {type(e).__name__}: {e}" + Fore.RESET)
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

        headers = {"ngrok-skip-browser-warning": "true"}
        
        # Use a context manager to ensure the connection is closed after reading the stream
        # Phase 2 will implement real-time streaming playback.
        with requests.post(endpoint, data=data, headers=headers, timeout=120, stream=True) as response:
            if response.status_code == 200:
                all_pcm = b""
                for chunk in response.iter_content(chunk_size=4096):
                    all_pcm += chunk

                # Wrap the collected PCM in a WAV header and save
                save_pcm_as_wav(all_pcm, output_path)
                return True
            else:
                if not get_setting("suppress_errors", False):
                    print(Fore.RED + f"[XTTS REMOTE ERROR] {response.status_code}: {response.text}" + Fore.RESET)
                return False

    except Exception as e:
        if not get_setting("suppress_errors", False):
            print(Fore.RED + f"[XTTS REMOTE ERROR] {e}" + Fore.RESET)
        return False
