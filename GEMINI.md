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

## Future Features & Memory
### Proposed: Image Bubble Support & Asynchronous Image Optimizer
- **Objective:** Add support for rendering image links/URLs directly in the chat interface using `textual-image` while preventing UI/rendering lag from large/high-res images.
- **Image Parsing & Rendering:**
  - Parse markdown image syntax `![alt](url)` and raw image links in messages.
  - Render dynamically using Sixel, Kitty, or Blocky protocol via `_resolve_image_widget_type()`.
  - Fall back gracefully to standard text layout (`🖼️ [Image: description]`) if terminal graphics are unsupported or turned off.
- **Async Optimizer Engine:**
  - When loading character/user portraits or chat bubble images, downscale them asynchronously (e.g. max dimension 500px to 800px) in a background Textual worker or thread.
  - Cache optimized copies in a local hidden directory (e.g. `.cache/optimized_images/`) to ensure fast loads on subsequent reads/scrolling.
  - Primary tool: **Pillow** (pre-installed, fast, cross-platform).
  - Secondary/Optional tool: **FFmpeg** via background `subprocess` for animated GIF formats.

### Proposed: AI-Assisted Character Card Refinement & Guardrails
- **Objective:** Utilize local LLMs (e.g. `llama3.2`, `dolphin-mistral`) to extract structured fields and clean up raw character data imported from external cards (e.g. SillyTavern JSON/PNG format).
- **Core Architecture:**
  - Execute a structured JSON schema extraction prompt against the local utility model.
  - Parse extracted data to fill in structured fields: `alt_names`, `personality_type`, `backstory`, `character_info` (gender, age, appearance, likes, dislikes), and conversational `rp_mannerisms`.
- **Implementation & Safety Guardrails:**
  - **JSON Enforcement:** Call local models with `format="json"` and sanitize outputs to prevent malformed bracket parsing errors.
  - **Strict Hallucination Grounding:** Direct the LLM in the system prompt to use "Unknown" or empty lists for unmentioned details instead of inventing them.
  - **Censorship Refusal Fail-Safe:** Detect refusal triggers ("I cannot fulfill", "Against safety guidelines") and fallback gracefully to the standard rule-based parse.
  - **Preserve Prompt Integrity:** Never let the AI modify core system instructions (`system_prompt`) or starter messages (`starter_messages`) to prevent loss of design intent.
  - **Async/Non-blocking Execution:** Execute the LLM queries inside background Textual workers/threads to keep the UI fully responsive with a non-blocking progress spinner/indicator.
