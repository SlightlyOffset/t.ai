"""
Text-to-Speech (TTS) engine.
Supports Microsoft Edge Neural TTS (online) and pyttsx3 (offline fallback).
Includes logic to strip or preserve RP narration from spoken audio.
"""

import os
import re
import time
import asyncio
import socket
import subprocess

from colorama import Fore
import shutil
from engines.config import get_setting
from engines.xtts_local import XTTSWorker, is_xtts_supported
from engines.audio_cache import get_cache_path, save_to_cache
from engines.utilities import log_debug

# Attempt to import edge-tts
try:
    import edge_tts
    EDGE_AVAILABLE = True
except ImportError:
    EDGE_AVAILABLE = False

# Fallback offline engine
try:
    import pyttsx3
    OFFLINE_AVAILABLE = True
except ImportError:
    OFFLINE_AVAILABLE = False

_offline_engine = None

def clean_text_for_tts(text: str, speak_narration: bool = True) -> str:
    """
    Cleans text for the TTS engine.
    Either strips narration (*...*) or just removes the symbols based on settings.

    Args:
        text (str): Raw segment of text from the LLM.
        speak_narration (bool): If True, removes symbols but keeps text. If False, strips text entirely.

    Returns:
        str: Cleaned text suitable for the TTS engine.
    """
    if speak_narration:
        # Just remove formatting symbols but keep the words
        cleaned = text.replace('***', '').replace('**', '').replace('*', '')
        cleaned = cleaned.replace('(', '').replace(')', '').replace('[', '').replace(']', '')
    else:
        # 1. Remove text inside triple or double asterisks first
        cleaned = re.sub(r'\*{2,3}.*?\*{2,3}', '', text, flags=re.DOTALL)
        # 2. Remove text inside single asterisks
        cleaned = re.sub(r'\*.*?\*', '', cleaned, flags=re.DOTALL)
        # 3. Remove text inside parentheses
        cleaned = re.sub(r'\(.*?\)', '', cleaned, flags=re.DOTALL)
        # 4. Remove text inside brackets
        cleaned = re.sub(r'\[.*?\]', '', cleaned, flags=re.DOTALL)

    # Final cleanup of leftover stray symbols and normalization
    cleaned = cleaned.replace('*', '').replace('[', '').replace(']', '')

    # Strip any stray file extensions that might have leaked in
    cleaned = re.sub(r'\.(wav|mp3|ogg|wav)\b', '', cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    # If the text is only punctuation/symbols, it's effectively empty for TTS
    if not any(c.isalnum() for c in cleaned):
        return ""

    return cleaned

def is_online(host="8.8.8.8", port=53, timeout=3):
    """Checks for an active internet connection."""
    try:
        socket.setdefaulttimeout(timeout)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.connect((host, port))
        return True
    except (socket.timeout, socket.error):
        return False

def get_offline_engine():
    """Initializes and returns the pyttsx3 engine."""
    global _offline_engine
    if _offline_engine is None and OFFLINE_AVAILABLE:
        try:
            default_rate = get_setting("tts_rate", 170)
            _offline_engine = pyttsx3.init()
            _offline_engine.setProperty('rate', default_rate)
        except:
            pass
    return _offline_engine

async def generate_edge_tts(text, filename, voice="en-GB-SoniaNeural"):
    """Internal async function for Edge TTS."""
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(filename)

def play_audio_windows(filename):
    """Plays audio via direct Windows Multimedia API integration (MCI) in-memory, avoiding VBScript."""
    abspath = os.path.abspath(filename)
    try:
        import ctypes
        from ctypes import wintypes
        
        winmm = ctypes.windll.winmm
        mciSendString = winmm.mciSendStringW
        mciSendString.argtypes = (wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.UINT, wintypes.HANDLE)
        mciSendString.restype = wintypes.DWORD

        alias = f"tts_audio_{int(time.time() * 1000)}"
        
        # open the file with mpegvideo type (works for both WAV and MP3)
        res = mciSendString(f'open "{abspath}" type mpegvideo alias {alias}', None, 0, None)
        if res != 0:
            # Fallback open without specifying a type
            res = mciSendString(f'open "{abspath}" alias {alias}', None, 0, None)
            
        if res == 0:
            # Play and block until finished (wait flag)
            mciSendString(f'play {alias} wait', None, 0, None)
            mciSendString(f'close {alias}', None, 0, None)
        else:
            raise Exception(f"MCI open failed with code {res}")
    except Exception as e:
        # Fallback to os.startfile
        try:
            os.startfile(abspath)
            time.sleep(2)  # Give it some time to start the player
        except Exception as fallback_err:
            print(Fore.RED + f"[PLAY ERROR] {e} (Fallback failed: {fallback_err})")

def resolve_voice_refs(clone_ref):
    """
    Resolves voice_clone_ref from a profile into a flat list of 3 WAV file paths.

    Accepts:
      - None                          → None
      - "voices/Astgenne"             → up to 3 .wav files inside that directory (sorted)
      - "voices/Astgenne/sample.wav"  → ["voices/Astgenne/sample.wav"]
      - ["voices/Astgenne", ...]      → expands any directories in the list

    Non-directory paths are passed through as-is; missing file validation is
    left to the downstream XTTS clients.
    """
    if not clone_ref:
        return None

    refs = clone_ref if isinstance(clone_ref, list) else [clone_ref]
    resolved = []
    for ref in refs:
        if os.path.isdir(ref):
            wavs = sorted(
                os.path.join(ref, f) for f in os.listdir(ref)
                if f.lower().endswith(".wav")
            )
            resolved.extend(wavs)
        else:
            resolved.append(ref)
    return resolved if resolved else None


def generate_audio(text, filename, voice=None, engine="edge-tts", clone_ref=None, language="en", user_name="User"):
    """
    Converts text to an MP3 or WAV file.
    Supports edge-tts (default) and XTTS.
    """
    if not get_setting("tts_enabled", True):
        return False

    # Resolve voice_clone_ref: expand directories to sorted WAV file lists
    clone_ref = resolve_voice_refs(clone_ref)

    cleaned_text = clean_text_for_tts(text, speak_narration=True)
    if not cleaned_text:
        return False

    log_debug("TTS_GEN_START", {"engine": engine, "text_len": len(cleaned_text), "voice": voice})

    if get_setting("debug_mode", False):
        print(Fore.MAGENTA + f"[DEBUG] Final TTS Text: '{cleaned_text}'" + Fore.RESET)

    # --- Cache Check ---
    # Determine cache key parameters
    cache_voice = voice if voice else "default"
    cache_key_engine = engine
    if engine == "xtts" and clone_ref:
        if isinstance(clone_ref, list):
            # Use parent dir name if all files share one directory, else join basenames
            dirs = set(os.path.dirname(p) for p in clone_ref)
            if len(dirs) == 1:
                ref_key = os.path.basename(list(dirs)[0])
            else:
                ref_key = "_".join(os.path.basename(p) for p in clone_ref)
        else:
            ref_key = os.path.basename(clone_ref)
        cache_key_engine = f"xtts_{ref_key}_{language}"


    # Check if we have this cached
    cached_path = get_cache_path(cleaned_text, cache_voice, cache_key_engine)

    if os.path.exists(cached_path):
        try:
            shutil.copy(cached_path, filename)
            log_debug("TTS_CACHE_HIT", {"path": cached_path})
            return True
        except Exception as e:
            print(Fore.YELLOW + f"[TTS CACHE] Failed to copy cache: {e}" + Fore.RESET)
    # -------------------

    # 1. Attempt XTTS if requested
    if engine == "xtts":
        xtts_success = False
        # Try Local first
        if is_xtts_supported() and clone_ref:
            try:
                # Ensure filename ends with .wav for XTTS if it doesn't already
                xtts_filename = filename if filename.endswith(".wav") else filename.replace(".mp3", ".wav")
                worker = XTTSWorker()
                if worker.generate(cleaned_text, xtts_filename, clone_ref, language=language):
                    # Save to cache
                    with open(xtts_filename, "rb") as f:
                        save_to_cache(cleaned_text, cache_voice, cache_key_engine, f.read())
                    xtts_success = True
            except Exception as e:
                log_debug("TTS_GEN_ERROR", {"engine": "xtts_local", "error": str(e)})
                if not get_setting("suppress_errors", False):
                    print(Fore.YELLOW + f"[XTTS LOCAL ERROR] {e}" + Fore.RESET)

        # Try Remote if Local failed or not available
        if not xtts_success and clone_ref and get_setting("remote_tts_url"):
            from engines.xtts_remote import generate_remote_xtts
            try:
                # Use .wav for remote generation to ensure compatibility, then rename back
                xtts_filename = filename if filename.endswith(".wav") else filename.replace(".mp3", ".wav")
                if generate_remote_xtts(cleaned_text, xtts_filename, clone_ref, language=language, user_name=user_name):
                    # Save to cache
                    if os.path.exists(xtts_filename):
                        with open(xtts_filename, "rb") as f:
                            save_to_cache(cleaned_text, cache_voice, cache_key_engine, f.read())
                        xtts_success = True
            except Exception as e:
                log_debug("TTS_GEN_ERROR", {"engine": "xtts_remote", "error": str(e)})
                if not get_setting("suppress_errors", False):
                    print(Fore.YELLOW + f"[XTTS REMOTE ERROR] {e}" + Fore.RESET)

        if xtts_success:
            # IMPORTANT: Ensure the file exists at the EXACT path requested by the caller
            if 'xtts_filename' in locals() and xtts_filename != filename:
                if os.path.exists(xtts_filename):
                    if os.path.exists(filename): os.remove(filename)
                    os.rename(xtts_filename, filename)
            log_debug("TTS_GEN_SUCCESS", {"engine": "xtts", "filename": filename})
            return True

        # Fallback to edge-tts if XTTS failed or not supported
        if not get_setting("suppress_errors", False):
            print(Fore.YELLOW + "[XTTS FALLBACK] Switching to Edge-TTS." + Fore.RESET)
        engine = "edge-tts"



    # 2. Attempt Edge-TTS
    if engine == "edge-tts":
        if not EDGE_AVAILABLE or not is_online():
            log_debug("TTS_GEN_ERROR", {"engine": "edge-tts", "error": "Edge-TTS not available or offline"})
            return False
        try:
            if voice is None:
                voice = get_setting("default_tts_voice", "en-GB-SoniaNeural")

            asyncio.run(generate_edge_tts(cleaned_text, filename, voice=voice))

            # Save to cache
            if os.path.exists(filename):
                with open(filename, "rb") as f:
                    save_to_cache(cleaned_text, cache_voice, cache_key_engine, f.read())

            log_debug("TTS_GEN_SUCCESS", {"engine": "edge-tts", "filename": filename})
            return True
        except Exception as e:
            log_debug("TTS_GEN_ERROR", {"engine": "edge-tts", "error": str(e)})
            if not get_setting("suppress_errors", False):
                print(Fore.RED + f"\n[TTS GEN ERROR] {e}")
            return False

    return False
def play_audio(filename):
    """Plays and deletes the audio file."""
    if not get_setting("tts_enabled", True):
        return
    log_debug("TTS_PLAY_START", {"filename": filename})
    try:
        import sys
        if sys.platform == "win32":
            play_audio_windows(filename)
        elif sys.platform == "darwin":
            # macOS: play silently in CLI using afplay (blocks until done)
            subprocess.run(["afplay", filename], check=True)
        elif sys.platform.startswith("linux"):
            # Linux: try paplay (for WAV), or mpg123 / aplay, or fallback to xdg-open
            played = False
            is_wav = filename.lower().endswith(".wav")
            if is_wav and shutil.which("paplay"):
                try:
                    subprocess.run(["paplay", filename], check=True)
                    played = True
                except subprocess.SubprocessError:
                    pass
            
            if not played and not is_wav and shutil.which("mpg123"):
                try:
                    subprocess.run(["mpg123", "-q", filename], check=True)
                    played = True
                except subprocess.SubprocessError:
                    pass

            if not played and is_wav and shutil.which("aplay"):
                try:
                    subprocess.run(["aplay", "-q", filename], check=True)
                    played = True
                except subprocess.SubprocessError:
                    pass

            if not played:
                # Fallback to xdg-open
                subprocess.run(["xdg-open", filename], check=True)
                time.sleep(2)
        else:
            # Generic POSIX fallback
            cmd = "xdg-open" if os.name == "posix" else "open"
            subprocess.run([cmd, filename])
            time.sleep(2)
        log_debug("TTS_PLAY_SUCCESS", {})
    except Exception as e:
        log_debug("TTS_PLAY_ERROR", {"error": str(e)})
        if not get_setting("suppress_errors", False):
            print(Fore.RED + f"\n[TTS PLAY ERROR] {e}")
    finally:
        if os.path.exists(filename):
            try: os.remove(filename)
            except: pass

def speak(text, pref_tts: str | None = None, engine="edge-tts", clone_ref=None, language="en"):
    """High-level synchronous speak function."""
    if not get_setting("tts_enabled", True):
        return

    filename = "temp_speak.mp3"
    if generate_audio(text, filename, voice=pref_tts, engine=engine, clone_ref=clone_ref, language=language):
        play_audio(filename)
    else:
        # Fallback to pyttsx3 if edge-tts/xtts failed and offline engine available
        if OFFLINE_AVAILABLE:
            cleaned_text = clean_text_for_tts(text, speak_narration=True)
            if cleaned_text:
                py_engine = get_offline_engine()
                py_engine.say(cleaned_text); py_engine.runAndWait()
