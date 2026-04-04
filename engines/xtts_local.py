"""
Local XTTS v2 inference module.
Optimized for NVIDIA GPUs with 6GB+ VRAM (e.g., RTX 3050).
"""

import os
import gc
from colorama import Fore

try:
    from TTS.api import TTS
    import torch
    XTTS_AVAILABLE = True
except ImportError:
    TTS = None
    torch = None
    XTTS_AVAILABLE = False

class XTTSWorker:
    _instance = None
    _model = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(XTTSWorker, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if not XTTS_AVAILABLE:
            return
        self.load_model()

    def load_model(self):
        """Loads the model to GPU memory if not already loaded."""
        if self._model is None and XTTS_AVAILABLE:
            try:
                from engines.config import get_setting
                print(Fore.CYAN + "[XTTS] Loading model to GPU..." + Fore.RESET)
                model_name = "tts_models/multilingual/multi-dataset/xtts_v2"
                self._model = TTS(model_name).to("cuda")
                print(Fore.GREEN + "[XTTS] Model loaded successfully." + Fore.RESET)
            except Exception as e:
                from engines.config import get_setting
                if not get_setting("suppress_errors", False):
                    print(Fore.RED + f"[XTTS ERROR] Failed to load model: {e}" + Fore.RESET)
                self._model = None

    def unload_model(self):
        """Unloads the model from GPU memory to free VRAM."""
        if self._model is not None:
            print(Fore.CYAN + "[XTTS] Unloading model from GPU..." + Fore.RESET)
            self._model = None
            gc.collect()
            if torch is not None and torch.cuda.is_available():
                torch.cuda.empty_cache()
            print(Fore.GREEN + "[XTTS] Model unloaded." + Fore.RESET)

    def generate(self, text, output_path, speaker_wav, language="en"):
        """
        Generates audio using local XTTS v2.
        speaker_wav can be a single path string or a list of paths for better cloning.
        """
        if self._model is None:
            self.load_model()
            
        if self._model is None:
            return False

        # Normalize to list — XTTS v2 accepts both but a list gives better results
        if isinstance(speaker_wav, str):
            speaker_wav = [speaker_wav]

        try:
            self._model.tts_to_file(
                text=text,
                speaker_wav=speaker_wav,
                language=language,
                file_path=output_path
            )
            return True
        except Exception as e:
            from engines.config import get_setting
            if not get_setting("suppress_errors", False):
                print(Fore.RED + f"[XTTS GEN ERROR] {e}" + Fore.RESET)
            return False

def is_xtts_supported():
    """Checks if XTTS dependencies are installed."""
    return XTTS_AVAILABLE
