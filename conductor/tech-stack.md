# Tech Stack - AI Desktop Companion

## Programming Languages
- **Python 3.10+**: Core application logic.
- **Jupyter Notebook (.ipynb)**: Used for the Colab-based remote inference bridge.

## AI and LLM (Inference)
- **Ollama**: Primary local LLM execution engine.
- **BitNet (1-bit LLM)**: Specialized lightweight models used for context summarization.
- **Google Colab (Remote)**: Supported for offloading LLM inference via the `LLM_Bridge.ipynb`, enabling usage on low-end hardware with limited VRAM.
- **ollama (library)**: Python bindings for Ollama API.

## Text-to-Speech (TTS)
- **edge-tts**: Primary engine using Microsoft Edge's high-fidelity neural voices.
- **XTTS v2**: High-fidelity voice cloning engine (Local CUDA or Remote Colab).
- **torch**: Deep learning framework required for XTTS.
- **TTS (library)**: Coqui TTS for voice cloning logic.
- **pyttsx3**: Fallback engine for local, offline TTS.

## User Interface
- **Terminal (CLI)**: Primary interaction layer.
- **colorama**: Terminal styling and ANSI color support.
- **textual-image**: Image rendering in Textual (Sixel/Kitty support).

## Data and Persistence
- **JSON**: Storage format for character profiles, user profiles, chat history, and application settings.
- **Lorebook (JSON)**: Structured format for world information with keyword triggers and prioritized insertion.

## Network and Communication
- **requests**: HTTP library for communication with local/remote LLM APIs.

## Target Platform
- **Windows (win32)**: Primary development and execution environment.
