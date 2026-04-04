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

# Attempt to import edge-tts
try:
    import edge_tts
    EDGE_AVAILABLE = True
except ImportError:
    EDGE_AVAILABLE = False

# Fallback offline engine (pyttsx3)
try:
    import pyttsx3
    OFFLINE_AVAILABLE = True
except ImportError:
    OFFLINE_AVAILABLE = False

# PyTorch/StyleTTS2 dependencies
try:
    import torch
except ImportError:
    pass

try:
    from styletts2 import tts
    STYLETTS2_AVAILABLE = True
except ImportError:
    STYLETTS2_AVAILABLE = False

_offline_engine = None
_styletts2_worker = None

class StyleTTS2Worker:
    """
    Singleton worker for StyleTTS 2.
    Loads the model once and provides an interface for inference.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(StyleTTS2Worker, cls).__new__(cls)
            cls._instance.model = None
            cls._instance.load_model()
        return cls._instance

    def load_model(self):
        if self.model is None and STYLETTS2_AVAILABLE:
            try:
                # Patch torch.load to bypass weights_only=True errors in PyTorch 2.6+
                # StyleTTS2 uses internal structures that weights_only doesn't yet support (e.g. defaultdict)
                import torch
                original_load = torch.load
                def patched_load(*args, **kwargs):
                    # Force weights_only to False regardless of if it was passed
                    kwargs['weights_only'] = False
                    return original_load(*args, **kwargs)
                
                torch.load = patched_load
                try:
                    # This will download the default LibriTTS checkpoint (~400MB) if not present
                    self.model = tts.StyleTTS2()
                finally:
                    torch.load = original_load
            except Exception as e:
                print(Fore.RED + f"[STYLETTS2 LOAD ERROR] {e}" + Fore.RESET)

    def generate(self, text, filename, target_voice_path=None):
        if self.model is None:
            return False
        try:
            # inference will save to filename. Note: StyleTTS2 typically outputs WAV.
            # We use diffusion_steps=5 for high speed/low VRAM as per plan.
            self.model.inference(
                text=text,
                target_voice_path=target_voice_path,
                output_wav_file=filename,
                diffusion_steps=5
            )
            return os.path.exists(filename)
        except Exception as e:
            print(Fore.RED + f"[STYLETTS2 GEN ERROR] {e}" + Fore.RESET)
            return False

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
    """Plays audio via VBScript or fallback on Windows."""
    abspath = os.path.abspath(filename)
    escaped_path = abspath.replace('\\', '\\\\')

    # Method 1: VBScript (Hidden playback)
    vbs_path = os.path.join(os.environ["TEMP"], f"play_sound_{int(time.time())}.vbs")
    vbs_content = f"""
    On Error Resume Next
    Set Sound = CreateObject("WMPlayer.OCX")
    If Err.Number <> 0 Then
        WScript.Quit 1
    End If
    Sound.settings.volume = 100
    Sound.URL = "{escaped_path}"
    Sound.Controls.play

    ' Wait for media to load (max 5 seconds)
    count = 0
    do while Sound.currentmedia.duration = 0 and count < 100
        wscript.sleep 50
        count = count + 1
    loop

    ' Play until finished (with a safety timeout)
    if Sound.currentmedia.duration > 0 then
        wscript.sleep (Sound.currentmedia.duration * 1000)
    else
        ' Fallback wait if duration is somehow not reported but it's playing
        wscript.sleep 2000
    end if
    """
    try:
        with open(vbs_path, "w") as f: f.write(vbs_content)
        # We use wscript.exe to run it. If it fails, subprocess will go to except.
        result = subprocess.run(["wscript.exe", vbs_path], capture_output=True, timeout=35)
        if result.returncode != 0:
            raise Exception("VBScript failed")
    except:
        # Method 2: os.startfile (Fallback)
        try:
            os.startfile(abspath)
            time.sleep(2) # Give it some time to start the player
        except Exception as e:
            print(Fore.RED + f"[PLAY ERROR] {e}")
    finally:
        if os.path.exists(vbs_path):
            try: os.remove(vbs_path)
            except: pass

def resolve_voice_refs(clone_ref):
    """
    Resolves voice_clone_ref from a profile into a flat list of WAV file paths.

    Accepts:
      - None                          → None
      - "voices/Astgenne"             → all .wav files inside that directory (sorted)
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


def generate_audio(text, filename, voice=None, engine="edge-tts", clone_ref=None, language="en"):
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
    elif engine == "styletts2" and clone_ref:
        # StyleTTS 2 usually takes a single WAV ref, but we handle lists too
        ref_key = os.path.basename(clone_ref[0] if isinstance(clone_ref, list) else clone_ref)
        cache_key_engine = f"styletts2_{ref_key}"

    # Check if we have this cached
    cached_path = get_cache_path(cleaned_text, cache_voice, cache_key_engine)

    if os.path.exists(cached_path):
        try:
            shutil.copy(cached_path, filename)
            return True
        except Exception as e:
            print(Fore.YELLOW + f"[TTS CACHE] Failed to copy cache: {e}" + Fore.RESET)
    # -------------------

    # 1. Attempt StyleTTS 2 if requested
    if engine == "styletts2":
        if STYLETTS2_AVAILABLE:
            try:
                # StyleTTS 2 outputs WAV
                st2_filename = filename if filename.endswith(".wav") else filename.replace(".mp3", ".wav")
                # Use the first reference if a list is provided
                target_ref = clone_ref[0] if isinstance(clone_ref, list) else clone_ref
                
                worker = StyleTTS2Worker()
                if worker.generate(cleaned_text, st2_filename, target_voice_path=target_ref):
                    # Save to cache
                    if os.path.exists(st2_filename):
                        with open(st2_filename, "rb") as f:
                            save_to_cache(cleaned_text, cache_voice, cache_key_engine, f.read())
                        
                        # Ensure filename is at the requested path
                        if st2_filename != filename:
                            if os.path.exists(filename): os.remove(filename)
                            os.rename(st2_filename, filename)
                        return True
            except Exception as e:
                if not get_setting("suppress_errors", False):
                    print(Fore.YELLOW + f"[STYLETTS2 ERROR] {e}" + Fore.RESET)
        
        # Fallback to edge-tts
        engine = "edge-tts"

    # 2. Attempt XTTS if requested
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
                if not get_setting("suppress_errors", False):
                    print(Fore.YELLOW + f"[XTTS LOCAL ERROR] {e}" + Fore.RESET)

        # Try Remote if Local failed or not available
        if not xtts_success and clone_ref and get_setting("remote_tts_url"):
            from engines.xtts_remote import generate_remote_xtts
            try:
                # Use .wav for remote generation to ensure compatibility, then rename back
                xtts_filename = filename if filename.endswith(".wav") else filename.replace(".mp3", ".wav")
                if generate_remote_xtts(cleaned_text, xtts_filename, clone_ref, language=language):
                    # Save to cache
                    if os.path.exists(xtts_filename):
                        with open(xtts_filename, "rb") as f:
                            save_to_cache(cleaned_text, cache_voice, cache_key_engine, f.read())
                        xtts_success = True
            except Exception as e:
                if not get_setting("suppress_errors", False):
                    print(Fore.YELLOW + f"[XTTS REMOTE ERROR] {e}" + Fore.RESET)

        if xtts_success:
            # IMPORTANT: Ensure the file exists at the EXACT path requested by the caller
            if 'xtts_filename' in locals() and xtts_filename != filename:
                if os.path.exists(xtts_filename):
                    if os.path.exists(filename): os.remove(filename)
                    os.rename(xtts_filename, filename)
            return True

        # Fallback to edge-tts if XTTS failed or not supported
        if not get_setting("suppress_errors", False):
            print(Fore.YELLOW + "[XTTS FALLBACK] Switching to Edge-TTS." + Fore.RESET)
        engine = "edge-tts"

    # 2. Attempt Edge-TTS
    if engine == "edge-tts":
        if not EDGE_AVAILABLE or not is_online():
            return False
        try:
            if voice is None:
                voice = get_setting("default_tts_voice", "en-GB-SoniaNeural")

            asyncio.run(generate_edge_tts(cleaned_text, filename, voice=voice))

            # Save to cache
            if os.path.exists(filename):
                with open(filename, "rb") as f:
                    save_to_cache(cleaned_text, cache_voice, cache_key_engine, f.read())

            return True
        except Exception as e:
            if not get_setting("suppress_errors", False):
                print(Fore.RED + f"\n[TTS GEN ERROR] {e}")
            return False

    return False
def play_audio(filename):
    """Plays and deletes the audio file."""
    if not get_setting("tts_enabled", True):
        return
    try:
        if os.name == "nt":
            play_audio_windows(filename)
        else:
            cmd = "xdg-open" if os.name == "posix" else "open"
            subprocess.run([cmd, filename])
            time.sleep(2)
    except Exception as e:
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
