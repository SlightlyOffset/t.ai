# 🤖 t.ai - Terminal AI Desktop Companion

**Current Status: [Stable v2.0.0](https://github.com/SlightlyOffset/t.ai/releases/tag/v2.0.0)**

A lightweight, highly immersive, profile-based AI companion that lives in your terminal. Built for roleplayers and AI enthusiasts who want a character that feels alive, remembers the past, and has a distinct personality.

---

## ✨ Key Features

### 🖥️ Modern TUI (Terminal User Interface)

* **Split-Pane Cards Layout**: A premium split horizontal dashboard displaying selectable character/user profiles on the left and a detailed scrollable info card (with background optimized avatars, biography, statistics, and likes/dislikes) on the right.
* **Minimalist Bubble Layout**: A clean, distraction-free chat interface with right-aligned user messages and left-aligned companion responses.
* **Sixel/Kitty Image Rendering**: High-fidelity character portraits integrated directly into the terminal for deeper immersion.
* **Real-time Streaming**: Watch your companion "think" and type in real-time within immersive side-bordered bubbles.
* **Immersive Styling**: Automatic italicization and dimming of RP narration (`*actions*`) to separate dialogue from description.
* **Live As-You-Type Highlight**: Real-time syntax highlighting in the chat input and message editor as you type. Highlights speech (`"dialogue"`, color-customized to active character/user profiles), narration (`*actions*`), and exposition (`(thoughts)`) dynamically.
* **In-App Message Editing & History Mutation**: Edit any sent or received message inline within the chat list. Changes are dynamically persisted to the session history.
* **Persistent Sidebars & Header Optimizations**: Real-time tracking of relationship scores, status labels, and active profiles (Toggle with `Ctrl+B`). Optimized rendering loops (clockless headers) to eliminate lagging and flickering.


### 🎙️ Advanced Audio & Voice Cloning

* **Multi-Voice TTS**: Automatically switches between a narrator voice for actions (`*...*`) and a character voice for dialogue.
* **Voice Cloning (XTTS v2)**: Clone distinct voices locally or via Colab, giving your companion a truly unique and realistic voice.
* **Hybrid Offloading**: Intelligent switching between local CPU/GPU and remote GPU pools (Colab/Kaggle) for zero-latency TTS playback.
* **Pipelined Streaming**: Uses a multi-threaded queue system to generate and play audio *while* the LLM is still typing. Zero latency.

### 📈 Relationship Engine

* **Persistence**: A -100 to +100 relationship meter that dictates the AI's tone, obedience, and conversation instructions.
* **Relationship Intensity Rules**: Leverages dynamic intensity states (defined in `relationship_intensity.json`) to adjust the system prompt and conversation instructions based on current scores.

### 🎭 Deep Character Immersion & Memory

* **Starter Message Pagination & AI Fallbacks**: Shuffles and exposes multiple companion greetings as swipe alternatives (`Alt+Right`/`Alt+Left`). Automatically generates brand-new scenarios in-character using previous attempts as examples once predefined options run out.
* **Rolling Summarization & Memory Core**: Automatically condenses long histories (>15 messages) into a "Memory Core" injected into every interaction to preserve long-term narrative recall.
* **Dynamic Lorebook (World Info)**: Efficiently injects relevant world or character facts into the LLM context based on keywords detected in the conversation.
* **Character-Scoped Session Management**: Organizes history into character-scoped subfolders (`history/<character>/<session>_history.json`). Features a comprehensive session manager (TUI via `Ctrl+T` or CLI via `//session`) to load, create, branch (optionally from a specific message index), rename, and delete sessions.
* **User Profile-Session Binding & Separation**: Sessions automatically bind to the user profile active during the conversation, seamlessly switching profiles when reloading. Automatically splits off and separates sessions on active user profile mismatch.
* **Legacy Auto-Migration**: Automatically and transparently migrates legacy flat history and backup files into the character-scoped directory structure on launch.

### 🔌 Plugin & Lifecycle Hook Architecture

* **Thread-safe Hook Registry**: Safely register callbacks with priority-sorted queues to run side-effects or pipe/mutate data dynamically.
* **Core Interceptors**: Lifecycle hooks injected at critical phases (e.g., `on_startup`, `on_ui_ready`, `on_user_message`, `before_prompt_build`, `before_tts`, and `after_llm_generation`).
* **Settings Integration**: Auto-scans the `plugins/` directory and renders corresponding configuration switches and inputs in the **Settings > Plugins** tab dynamically based on `plugin.json` schemas.
* **Isolated Loading**: Loads plugins as isolated sub-packages of the `plugins` package to prevent namespace collisions and avoid modifying `sys.path`.

### 🎭 Creating & Importing Characters

t.ai is highly customizable. You can import existing characters from the AI community or build your own from scratch.

### 1. Importing SillyTavern Cards

You can import `.png` character cards or `.json` definitions directly into the app:

* **In-App**: Type `//import_card "C:\path\to\character.png"` while the chat is running.
* **Batch**: Use the standalone `python card_importer.py` script to import entire directories of cards.

### 2. Creating Custom Profiles

To create a unique character or your own user profile, use the JSON templates found in the `template/` directory as a baseline.

* **Character Profiles**: Copy `template/character_template.json` to the `profiles/` folder and rename it (e.g., `MyHero.json`).
  * Fill in the `name`, `backstory`, and `system_prompt`.
  * Set `preferred_edge_voice` or configure `voice_clone_ref` for XTTS voice cloning.
* **User Profiles**: Copy `template/user_template.json` to the `user_profiles/` folder. This helps the AI remember *your* name, appearance, and personality.
* **Lorebooks**: Use `template/lorebook_template.json` in the `lorebooks/` folder to create world-info triggers that inject context when specific keywords are mentioned.

### 3. Voice Cloning Setup (XTTS)

To give your character a specific voice:

1. Create a folder in `voices/` (e.g., `voices/MyHero/`).
2. Add one or more `.wav` samples of the voice (short clips, clean audio).
3. In your character's `.json` profile, set `"tts_engine": "xtts"` and `"voice_clone_ref": "voices/MyHero"`.

---

## ☁️ Remote Inference & GPU Offloading

If you have limited VRAM (less than 8GB) or want to use high-fidelity voice cloning (XTTS v2) without slowing down your PC, you can offload the "brain" and "voice" of your companion to Google Colab or Kaggle.

### 🛠️ Setting up the Bridge

1. **Open the Notebook**: Upload the `.ipynb` files from the `/colab_bridge` folder to Google Colab or Kaggle.
   * `LLM_Bridge.ipynb`: For remote LLM inference (Stheno, Llama 3, etc.).
   * `XTTS_Bridge.ipynb`: For high-speed voice cloning.
2. **GPU Check**: Ensure your runtime type is set to **GPU** (T4 or better).
3. **Configure Secrets**:
   * Add your `HF_TOKEN` (Hugging Face) to the notebook "Secrets" or "Add-ons" section to allow model downloads.
4. **Run All**: Execute all cells in the notebook.
5. **Get the URL**: Wait for the **🚀 BRIDGE ONLINE!** message at the bottom. It will provide a Cloudflare tunnel URL (e.g., `https://random-words.trycloudflare.com`).

### 🔗 Connecting to t.ai

Open your local `settings.json` and paste the generated URLs:

```json
{
  "remote_llm_url": "https://your-llm-bridge-url.trycloudflare.com",
  "remote_tts_url": "https://your-xtts-bridge-url.trycloudflare.com"
}
```

*Note: Remote inference features automatic OOM retries, context truncation, and semantic RAG support parity with the local engine.*

---

## 🛠️ Model Context Protocol (MCP) & Tool Calling

`t.ai` supports the Model Context Protocol (MCP) to allow tool-capable local models (like `Qwen 2.5` or `Hermes 3`) to execute external system tools dynamically during chat.

### Hybrid Command & Tool Architecture
1. **Deterministic Slash Commands**: Commands like `//import_card <path> [--refine|-r]` execute safely in a background thread to prevent UI freezing, outputting live refinement progress directly inside the TUI console. They work regardless of what chat model you have loaded.
2. **Conversational Tool Calling**: If your active chat model supports tool-calling, your companion can automatically run tools (e.g. `import_st_card`) conversationally mid-chat when you request it. If the active model does not support tool calling (like `fluffy/l3-8b-stheno-v3.2`), the app automatically intercepts the API rejection and transparently falls back to regular text generation without crashing.

### VRAM & Model Recommendations (e.g., 6GB VRAM GPUs)
Running 8B parameter models with tool-calling capabilities alongside OS desktop overhead can exceed VRAM limits, causing **VRAM spillover** into system RAM (Shared memory) and slowing down token generation speeds to a crawl.
* **Recommended Utility Model**: For background tasks (like character card imports and refinements), set `local_utility_model` in `settings.json` to **`qwen2.5:3b`**. At ~2.2 GB, it fits entirely on the GPU (leaving room for Windows desktop overhead) and has excellent tool-calling and JSON extraction precision.
* **Hermes 3 (8B)**: If you prefer Hermes 3, pull the 3-bit version to avoid VRAM spillover: `ollama pull hermes3:8b-q3_K_M`.
* **Uncensored Options**: If you need a fully uncensored utility model, use `hermes3:8b-q3_K_M` or a Dolphin fine-tune.
* **VRAM Optimization Settings**:
  * Set `"unload_tts_after_generation": true` in `settings.json` (or via **Settings > TTS / Audio > Auto-Unload Local TTS**) to automatically unload local XTTS models from GPU memory immediately after audio generation, freeing VRAM for the LLM.
  * Set `"max_input_tokens"` (e.g., `4096` or `6200`) in `settings.json` (or via **Settings > Default Backend > Max Context Tokens**) to cap context-window usage and prevent massive prompt payloads from causing OOM or spillover.
  * Set `"local_llm_keep_alive": "5m"` (or set to `"0"` to unload immediately) to manage how long Ollama caches models in VRAM.

---

## 🔒 Security & Privacy

* **Privacy-First Design**: Mandatory HTTPS for remote services and secure masking of API tokens/sensitive keys in the UI.
* **Security Hardened**: Recently completed a comprehensive remediation sprint (May 2026) to address prompt injection (VULN-001), path traversal (VULN-003), and privacy leaks (VULN-004).
* **Isolated Data**: All history and settings are scoped to the active profile to prevent cross-character data leakage.

---

## 🚀 Getting Started

### Prerequisites

* **Python 3.10+**
* **Ollama** (Local LLM runner)
* **Terminal with Sixel/Kitty support** (e.g., WezTerm, Alacritty, iTerm2) for image rendering.

### 💻 System Requirements

* **Minimum (Local Inference)**: NVIDIA RTX 3050 (6GB VRAM).
  * *Required to run the recommended Llama 3 8B models locally with acceptable latency.*
* **Low-End Hardware**: If you have <6GB VRAM or no dedicated GPU, you **must** use the Remote Inference Bridge(see above) (Colab/Kaggle) for a smooth experience.

### Installation

1. **Clone the repo:**

    ```bash
    git clone https://github.com/SlightlyOffset/t.ai.git
    cd t.ai
    ```

2. **Install dependencies:**

    ```bash
    pip install -r requirements.txt
    ```

3. **Pull the recommended model:**

    ```bash
    ollama pull fluffy/l3-8b-stheno-v3.2
    ```

### Running the Companion

Simply run the main launcher to start the TUI:

```bash
python main.py
```

---

## 🎮 Commands & Shortcuts

Inside the chat, you can use operational commands or keyboard shortcuts:

* `Ctrl+B`: Toggle sidebar visibility.
* `Ctrl+S`: Open settings configuration window.
* `Ctrl+T`: Open the session selection and management modal screen.
* `Double-Click` or `e` (on a message bubble): Edit the message inline.
  * `Ctrl+S` (while editing): Save modifications and atomically update history.
  * `Esc` (while editing): Revert changes and exit edit mode.
* `//help`: Show all commands.
* `//settings`: Open the tabbed configuration settings screen.
* `//mode [rp|casual]`: Displays or changes the active interaction mode.
* `//toggle <setting>`: Toggles a boolean setting (e.g., `tts`, `speak`, `narration`, `errors`, `privacy`, `debug`).
* `//change <char|user> <name>`: Swap to a different character or user profile.
* `//session [list|current|new|load|branch|rename|delete]`: Command-line session manager to list, load, create, branch, rename, or delete conversation sessions.
* `//reset [all|rel]`: Reset chat history recursively across all sessions (all) or reset relationship scores (rel).
* `//import_card <path>`: Imports a SillyTavern character card.

---

## 🛠️ Configuration

Edit `settings.json` to customize your experience:

* `remote_llm_url` / `remote_tts_url`: Set these to your Colab/Kaggle tunneling endpoints for cloud offloading.
* `image_protocol`: Choose avatar rendering protocol (`auto`, `kitty`, `sixel`, `blocky`).
* `auto_recap_on_start`: Let the AI summarize the previous chat context upon booting.
* `privacy_mode`: Redact sensitive information from being sent to remote LLMs.
* `max_input_tokens`: Maximum context window length in tokens sent to the LLM (default `6200`).
* `local_llm_keep_alive`: Ollama model keep-alive duration (e.g. `"5m"`, or `"0"` to unload immediately).
* `unload_tts_after_generation`: Auto-unload the local XTTS model from VRAM after generating speech (default `false`).

---

## 📜 Roadmap

* [x] **Core Logic**: Relationship Engine and Persistent Memory (mood engine decoupled for future reimplementation).
* [x] **Cloud & Audio**: Colab Bridge, Streaming TTS, and XTTS v2 Integration.
* [x] **TUI Overhaul**: High-fidelity bubble layout and terminal image rendering.
* [x] **Security Sprint**: Comprehensive vulnerability remediation and hardening.
* [ ] **Agentic Intelligence (v2.0.0)**: Transform t.ai into an autonomous agent (File I/O, Code Execution).
* [ ] **Dedicated Command Mode**: Structured `Ctrl+!` input for complex task handling.
* [ ] **Live2D Integration**: Map relationship scores and future emotional states to sprite changes and animations.
