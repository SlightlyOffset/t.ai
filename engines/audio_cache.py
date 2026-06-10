"""
Audio caching system for TTS.
Stores generated audio files based on a hash of their content, voice, and engine.
"""

import os
import hashlib

CACHE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".cache", "audio"))

def _ensure_cache_dir(directory):
    if not os.path.exists(directory):
        os.makedirs(directory, exist_ok=True)

_ensure_cache_dir(CACHE_DIR)


def _get_hash(text, voice, engine):
    """Generates a unique MD5 hash for the given TTS parameters."""
    content = f"{text}|{voice}|{engine}".encode("utf-8")
    return hashlib.md5(content).hexdigest()

def get_cache_path(text, voice, engine, cache_dir=CACHE_DIR):
    """
    Returns the expected file path for a cached audio clip.
    """
    _ensure_cache_dir(cache_dir)
    file_hash = _get_hash(text, voice, engine)
    return os.path.join(cache_dir, f"{file_hash}.wav")

def save_to_cache(text, voice, engine, audio_data, cache_dir=CACHE_DIR):
    """
    Saves audio data to the cache.
    """
    path = get_cache_path(text, voice, engine, cache_dir)
    with open(path, "wb") as f:
        f.write(audio_data)
    return path
