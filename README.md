# 🤖 t.ai - Terminal AI Desktop Companion

A lightweight, highly immersive, profile-based AI companion that lives in your terminal. Built for roleplayers and AI enthusiasts who want a character that feels alive, remembers the past, and has a distinct personality.

***Note**: Definitely not c.ai but just to spite how c.ai is undergoing an enshitification cycle.*

---

## ✨ Key Features

### 🖥️ Modern TUI (Terminal User Interface)

* **Minimalist Bubble Layout**: A clean, distraction-free chat interface with right-aligned user messages and left-aligned companion responses.
* **Real-time Streaming**: Watch your companion "think" and type in real-time within immersive side-bordered bubbles.
* **Immersive Styling**: Automatic italicization and dimming of RP narration (`*actions*`) to separate dialogue from description.
* **Persistent Sidebars**: Real-time tracking of relationship scores, mood labels, and active profiles.

### 🎙️ Advanced Audio & Voice Cloning

* **Multi-Voice TTS**: Automatically switches between a narrator voice for actions (`*...*`) and a character voice for dialogue.
  * *Note: Using the **XTTS Colab Bridge** is highly recommended for voice cloning. Local installation is complex and resource-heavy, while the bridge provides high-speed GPU inference for free.*
* **Voice Cloning (XTTS v2)**: Clone distinct voices locally or via Colab, giving your companion a truly unique and realistic voice.
* **Edge Neural Support**: Built-in support for Microsoft's high-fidelity neural voices as a lightweight fallback.
* **Pipelined Streaming**: Uses a multi-threaded queue system to generate and play audio *while* the LLM is still typing. Zero latency.

### 📈 Relationship & Mood Engine

* **Persistence**: A -100 to +100 relationship meter that dictates the AI's tone and obedience.
* **Mood Decay**: The character remembers how long it's been since you last chatted. If you disappear for days, their feelings will shift back toward neutral.
* **Sentiment Awareness**: The AI self-reports its emotional state based on your interactions, updating its profile in real-time.

### 🎭 Deep Character Immersion & Memory

* **Enriched Profiles**: Characters have backstories, physical appearances, likes/dislikes, and specific mannerisms they weave into their roleplay.
* **Persistent History & Recaps**: Saves chat history persistently per profile and automatically generates a recap of your previous session on startup.
* **User Profiles**: Support for detailed User Profiles so the AI knows exactly who it's talking to (custom user tracking).

---

## 🚀 Getting Started

### Prerequisites

* **Python 3.10+** (Recommended: 3.10.11 for the best compatibility)
* **Ollama** (Local LLM runner)
* **Microsoft Edge** (For neural TTS fallback)
* *(Optional)* **Google Colab account** for cloud offloading.

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

Simply run the main launcher to perform dependency checks and start the TUI:

```bash
python main.py
```

*(Note: The old CLI is still available via `python legacy_main.py` for reference.)*

*(If using the Colab Bridge, start the respective Jupyter notebooks in `/colab_bridge` first, and update your `settings.json` with the generated tunneling URLs.)*

---

## 🎭 Importing Characters

You can easily import character profiles from other sources. The importer is designed to work with **SillyTavern** character cards (`.png`) and character definitions (`.json`).

There are two ways to import a character:

### 1. In-App Command

While running the CLI/TUI application, use the `//import_card` command followed by the file path:

``` text
//import_card "C:\path\to\your\character.png"
```

The new profile will be added to your `profiles` directory and will be available the next time you use the `//change_character` command.

1. Standalone Importer Script

If you want to import multiple cards without running the main CLI/TUI, you can use the standalone `card_importer.py` script.

1. Run the script from your terminal:

    ```bash
    python card_importer.py
    ```

2. Follow the prompt to import a single card or a whole directory:
    * **Single Import**: `//import "C:\path\to\character.png"`
    * **Batch Import**: `//batch_import "C:\path\to\characters_folder"`

This provides a quick way to batch-import your character library.

**Note**: The conversion will likely be imperfect, review the output for any errors and adjust accordingly.

---

## 🎮 Commands

Inside the chat, you can use the following operational commands:

* `//help`: Show all commands.
* `//mode`: Toggle between RP and Casual modes.
* `//reset`: Clear the current conversation history.
* `//change_character`: Swap to a different character profile.
* `//change_user_profile`: Swap to a different user profile.
* `//import_card <path>`: Imports a character card. See the "Importing Characters" section for details.
* `//show_settings`: View current app configuration.
* `//toggle_clear_on_start`: Toggle console clearing at launch.
* `//restart`: Cleanly reboot the application.

---

## 🛠️ Configuration

Edit `settings.json` to customize your experience:

* `remote_llm_url` / `remote_tts_url`: Set these to your Colab tunneling endpoints for cloud offloading.
  * `remote_llm_url` supports both JSON-chat envelopes and plain-text bridge responses for non-stream calls (candidate/critic/summarizer stages).
* `tts_enabled`: Toggle voice entirely on/off.
* `speak_narration`: Choose if the Narrator should speak the actions or only text dialogue.
* `memory_limit`: Control short-term memory limit (messages fed per prompt).
* `auto_recap_on_start`: Let the AI summarize the previous chat context upon booting.
* `interaction_mode`: Set default mode (`rp` or `casual`).

---

## 📜 Roadmap

* [x] **Phase 1-3**: Core Terminal logic, Mood Engine, Persistent Memory, Profiles, and Relationships.
* [x] **Phase 4**: Cloud Computing (Colab Bridge), Voice & Response Streaming, Session Recaps, and Voice Cloning (XTTS v2).
* [x] **Phase 5 (Alpha)**: TUI Overhaul (**t.ai**), Dynamic Scene Memory, and mood-locked RP.
* [ ] **Live2D Integration**: Map mood scores and sentiment to sprite changes and animations.
* [ ] **Speech-to-Text**: Full voice control for hands-free conversations.
* [ ] **Context Summarization**: Long-term memory compression via automated summaries.

---

## 🤝 Contributing

Feel free to fork, submit PRs, or suggest personalities.

*Disclaimer: This is an early build codebase. Expect some quirks.*

---

### 💖 Made with love by [@SlightlyOffset](https://github.com/SlightlyOffset). And thanks to my swamp of AI slaves for their support
