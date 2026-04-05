# 🎙️ Voice Cloning Implementation Plan (XTTS v2)

## 📋 Overview

To implement high-quality voice sampling on an **RTX 3050 (6GB VRAM)**, we will offload the LLM "brain" to **Google Colab** and use the local GPU exclusively for the **XTTS v2** voice cloning engine.

---

## 🛠️ Step 1: Environment Setup

* **Dependencies**: Install `coqui-tts` and `ffmpeg`.
  * `pip install TTS`
  * Ensure `ffmpeg` is installed and in the System PATH.
* **VRAM Management**:
  * LLM must be running via `remote_llm_url` (Colab).
  * Local Ollama should be stopped to free up 6GB VRAM for XTTS.

## 🎤 Step 2: Voice Sampling

* **Reference Audio**: Requires a 10-20 second `.wav` file of the target voice.
* **Storage**: Create a `/voices` directory to hold reference samples (e.g., `voices/manganese_ref.wav`).
* **Quality**: Sample must be clean (no background music/noise), 22050Hz or 44100Hz preferred.

## 💻 Step 3: Code Integration (`engines/tts_module.py`)

* **Model Initialization**:
  * Add a `XTTSWorker` class or update `tts_module.py` to load the `TTS` model onto `cuda`.
  * Implement a singleton pattern to ensure the model only loads once.
* **Generation Logic**:
  * Update `generate_audio` to accept a `use_cloning` flag.
  * If `use_cloning` is True, use `tts.tts_to_file(...)` with the `speaker_wav` reference.
* **Fallback**: Maintain `edge-tts` as a fallback if the local GPU is overloaded or the model fails to load.

## ⚙️ Step 4: Configuration (`settings.json`)

* Add new keys:
  * `"use_local_cloning": true`
  * `"cloning_reference_file": "voices/sample.wav"`
  * `"xtts_model_path": "tts_models/multilingual/multi-dataset/xtts_v2"`

---

## 🔄 Workflow

1. **User** starts Colab Bridge and updates `remote_llm_url`.
2. **App** starts and initializes XTTS v2 on the RTX 3050.
3. **LLM** (Colab) generates a response.
4. **TTS** (Local) receives text and clones the voice using the reference `.wav`.
5. **Audio** plays with zero-latency streaming.
