# 🤖 t.ai - Terminal AI Desktop Companion

**Current Status: [Alpha 0.1.2 Hotfix](https://github.com/SlightlyOffset/t.ai/releases/tag/v0.1.2-alpha)**

A lightweight, highly immersive, profile-based AI companion that lives in your terminal. Built for roleplayers and AI enthusiasts who want a character that feels alive, remembers the past, and has a distinct personality.

---

## ✨ Key Features

### 🖥️ Modern TUI (Terminal User Interface)

* **Minimalist Bubble Layout**: A clean, distraction-free chat interface with right-aligned user messages and left-aligned companion responses.
* **Sixel/Kitty Image Rendering**: High-fidelity character portraits integrated directly into the terminal for deeper immersion.
* **Real-time Streaming**: Watch your companion "think" and type in real-time within immersive side-bordered bubbles.
* **Immersive Styling**: Automatic italicization and dimming of RP narration (`*actions*`) to separate dialogue from description.
* **Persistent Sidebars**: Real-time tracking of relationship scores, status labels, and active profiles (Toggle with `Ctrl+B`).

### 🎙️ Advanced Audio & Voice Cloning

* **Multi-Voice TTS**: Automatically switches between a narrator voice for actions (`*...*`) and a character voice for dialogue.
* **Voice Cloning (XTTS v2)**: Clone distinct voices locally or via Colab, giving your companion a truly unique and realistic voice.
* **Hybrid Offloading**: Intelligent switching between local CPU/GPU and remote GPU pools (Colab/Kaggle) for zero-latency TTS playback.
* **Pipelined Streaming**: Uses a multi-threaded queue system to generate and play audio *while* the LLM is still typing. Zero latency.

### 📈 Relationship Engine

* **Persistence**: A -100 to +100 relationship meter that dictates the AI's tone, obedience, and conversation instructions.
* **Relationship Intensity Rules**: Leverages dynamic intensity states (defined in `relationship_intensity.json`) to adjust the system prompt and conversation instructions based on current scores.

### 🎭 Deep Character Immersion & Memory

* **Rolling Summarization & Memory Core**: Automatically condenses long histories (>15 messages) into a "Memory Core" injected into every interaction to preserve long-term narrative recall.
* **Dynamic Lorebook (World Info)**: Efficiently injects relevant world or character facts into the LLM context based on keywords detected in the conversation.
* **Persistent History & Recaps**: Saves chat history persistently per profile and automatically generates a recap of your previous session on startup.

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
* `//help`: Show all commands.
* `//mode`: Toggle between RP and Casual modes.
* `//change <char|user>`: Swap to a different character or user profile.
* `//import_card <path>`: Imports a SillyTavern character card.
* `//restart`: Cleanly reboot the application.

---

## 🛠️ Configuration

Edit `settings.json` to customize your experience:

* `remote_llm_url` / `remote_tts_url`: Set these to your Colab/Kaggle tunneling endpoints for cloud offloading.
* `image_protocol`: Choose avatar rendering protocol (`auto`, `kitty`, `sixel`, `blocky`).
* `auto_recap_on_start`: Let the AI summarize the previous chat context upon booting.
* `privacy_mode`: Redact sensitive information from being sent to remote LLMs.

---

## 📜 Roadmap

* [x] **Core Logic**: Relationship Engine and Persistent Memory (mood engine decoupled for future reimplementation).
* [x] **Cloud & Audio**: Colab Bridge, Streaming TTS, and XTTS v2 Integration.
* [x] **TUI Overhaul**: High-fidelity bubble layout and terminal image rendering.
* [x] **Security Sprint**: Comprehensive vulnerability remediation and hardening.
* [ ] **Agentic Intelligence (v0.2.0)**: Transform t.ai into an autonomous agent (File I/O, Code Execution).
* [ ] **Dedicated Command Mode**: Structured `Ctrl+!` input for complex task handling.
* [ ] **Live2D Integration**: Map relationship scores and future emotional states to sprite changes and animations.
