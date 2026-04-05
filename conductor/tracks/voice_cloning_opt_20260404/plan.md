# Implementation Plan: Voice Cloning Optimization

## Phase 1: Bridge Server Refactoring (Colab)
*   [x] Update `XTTS_Bridge.ipynb` to add a persistent `speakers/` storage directory.
*   [x] Implement `/check_speaker/{speaker_id}` endpoint to check for existence.
*   [x] Implement `/upload_speaker` endpoint to store `.wav` files.
*   [x] Modify `/generate_tts` to accept `speaker_id` instead of a file upload.
*   [x] Refactor `/generate_tts` for **streaming output**.
    *   [x] Use `tts_model.inference_stream(...)` to yield audio chunks.
    *   [x] Return a `StreamingResponse`.

## Phase 2: Client Update (Local)
*   [x] Update `engines/xtts_remote.py` to:
    *   [x] Implement `ensure_voice_on_bridge(bridge_url, speaker_id, speaker_wavs)`.
    *   [x] Update `generate_remote_xtts` to send `speaker_id` rather than raw files.
*   [~] Implement **streaming playback support** in `engines/tts_module.py` and `engines/xtts_remote.py`.
    *   [x] Wrapped raw PCM in WAV header for immediate compatibility.
    *   [ ] Future: Use a real-time streaming player (like PyAudio or sounddevice) to start playback *during* the download.

## Phase 3: VRAM & Cleanup
*   [x] Update `XTTSWorker` in `engines/xtts_local.py` to support explicit unloading/loading of the model to free VRAM for the local LLM.
*   [ ] Test the full loop with a local LLM running.

## Verification & Testing
*   [ ] Verify `/check_speaker` correctly reports missing/existing speakers.
*   [ ] Verify `/upload_speaker` correctly saves multiple `.wav` files.
*   [ ] Verify the first generation triggers an upload and subsequent ones do not.
*   [ ] Measure time-to-first-sound to confirm < 2s latency.
