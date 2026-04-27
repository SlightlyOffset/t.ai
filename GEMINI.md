# Gemini Context: t.ai (Terminal AI Companion)

This project is a lightweight, immersive, terminal-based AI companion featuring high-fidelity TTS, dynamic mood/relationship engines, and deep character persistence.

## Project Overview
- **Purpose:** Provide a deeply immersive roleplay and conversation experience directly in the terminal.
- **Primary Framework:** [Textual](https://textual.textualize.io/) (Python TUI framework).
- **Core Technologies:**
    - **LLM Engine:** [Ollama](https://ollama.com/) (local) or Remote Colab Bridge (via `requests`).
    - **TTS Engine:** `edge-tts` (Microsoft Neural), `XTTS v2` (Voice Cloning), and `pyttsx3` (Offline fallback).
    - **Audio Pipeline:** Multi-threaded streaming queue for zero-latency TTS playback during LLM generation.
    - **Memory System:** Persistent JSON-based chat history with session recaps and "Memory Core" injection.
    - **Visuals:** [textual-image](https://github.com/darrenburns/textual-image) for Sixel/Kitty image rendering in the terminal.

## Architecture
The codebase is strictly divided into two layers:
1.  **UI Layer (`menu.py`, `ProfileSelectScreen.py`):** Handles terminal rendering, user input, and event management using Textual.
2.  **Engine Layer (`engines/`):** Contains the business logic:
    - `responses.py`: LLM interaction, sentiment analysis, and relationship scoring.
    - `response_orchestrator.py`: Orchestrates parallel LLM streaming and TTS queuing.
    - `memory_v2.py`: Manages persistent conversation history and state.
    - `tts_module.py`: Handles audio generation and hardware-specific playback.
    - `lorebook.py`: Dynamic context injection based on keyword triggers.
    - `config.py`: Global settings management via `settings.json`.

## Key Commands & Workflow
### Running the App
- **Primary Launcher:** `python main.py` (Performs dependency checks and launches TUI).
- **Legacy CLI:** `python legacy_main.py` (Old reference implementation).
- **Character Importer:** `python card_importer.py` (Standalone utility for SillyTavern cards).

### Development & Testing
- **Dependencies:** `pip install -r requirements.txt`
- **Recommended Model:** `ollama pull fluffy/l3-8b-stheno-v3.2`
- **Testing:** Uses `pytest`. Run `pytest tests/` to verify engine components.
- **Environment:** Requires Python 3.10+.

## Coding Conventions
- **UI/Logic Separation:** Never mix UI-specific code (Textual widgets/actions) directly into the `engines/` modules. Use events or orchestrators to bridge them.
- **Atomic Persistence:** Use `engines.utilities.save_json_atomic` for saving profiles and history to prevent corruption.
- **Async & Threading:** The app relies heavily on `textual.work` and `threading.Thread` for non-blocking TTS and LLM operations. Ensure thread safety when modifying shared state.
- **Profile Scope:** All history, memory, and settings should be scoped to the active `history_profile_name` or `user_profile`.

## File Structure Highlights
- `/profiles`: Character `.json` definitions.
- `/user_profiles`: User `.json` definitions.
- `/history`: Persistent chat logs.
- `/lorebooks`: World-info triggers.
- `/tcss`: Stylesheets for the Textual UI.
- `/colab_bridge`: Notebooks for offloading inference to GPU-enabled cloud environments.
