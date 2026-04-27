# Specification: Voice Cloning Optimization (Cached Speaker & Streaming)

## 📋 Overview
This track focuses on optimizing the **Local LLM + Remote XTTS** split to reduce the "Upload Tax" and "Generation Wait" times.

## 🛠️ Requirements

### 1. Cached Speaker System
*   **Bridge (Colab):** Add `/check_speaker` (GET) and `/upload_speaker` (POST) endpoints.
*   **Bridge (Colab):** Persistently store speaker `.wav` files in a `speakers/<speaker_id>` directory.
*   **Client (Local):** Before generating, check if the bridge already has the voice. If not, upload it once.
*   **Client (Local):** Subsequent requests only send `text` and `speaker_id`.

### 2. Audio Streaming
*   **Bridge (Colab):** Refactor the generation logic to use a **Generator** that yields audio chunks.
*   **Bridge (Colab):** Switch from `FileResponse` to a streaming response (e.g., `StreamingResponse` in FastAPI).
*   **Client (Local):** Update `xtts_remote.py` to handle chunked responses and stream them to the playback engine.

### 3. VRAM Hygiene
*   **Client (Local):** Ensure local TTS models (if any) are unloaded when using remote mode to save VRAM for the local LLM.

## 🎯 Success Criteria
*   **Latency Reduction:** Reduce time-to-first-sound for remote XTTS from ~10s to < 2s.
*   **Bandwidth Efficiency:** Eliminate redundant multi-megabyte uploads for every turn.
*   **Stability:** Ensure the system handles Colab restarts gracefully by re-uploading voices when needed.
