# 🤖 Terminal-based AI Desktop Companion

A lightweight, highly immersive, profile-based AI companion that lives in your terminal. Built for roleplayers and AI enthusiasts who want a character that feels alive, remembers the past, and has a distinct personality.

---

## ✨ Key Features

### 🎙️ Advanced Audio & Voice Cloning

* **Multi-Voice TTS**: Automatically switches between a narrator voice for actions (`*...*`) and a character voice for dialogue.
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
* **Roleplay Preservation**: Advanced regex and smart-splitting ensure that narration is styled correctly (Italics/Grey) and filtered properly for the voice engine.

### ⚡ Technical Efficiency & Cloud Offloading

* **Colab Bridge**: Offload the LLM or XTTS generation to Google Colab using included Jupyter notebooks (`/colab_bridge`). This frees up your local VRAM and allows running heavy models (e.g., 40B models or XTTS v2) on modest hardware.
* **CLI First**: No heavy GUI overhead. Beautiful terminal rendering with dynamic colors and styles.
* **Hybrid LLM Support**: Optimized for **Ollama** (specifically tested with Llama-based models) but natively supports remote APIs and Colab endpoints.

---

## 🚀 Getting Started

### Prerequisites

* **Python 3.11.10** (recommended)
* **Ollama** (Local LLM runner)
* **Microsoft Edge** (For neural TTS fallback)
* *(Optional)* **Google Colab account** for cloud offloading.

### Installation

1. **Clone the repo:**

    ```bash
    git clone https://github.com/SlightlyOffset/AI-companion.git
    cd AI-companion
    ```

2. **Install dependencies:**

    ```bash
    pip install colorama ollama requests edge-tts pyttsx3
    ```

3. **Pull the recommended model:**

    ```bash
    ollama pull fluffy/l3-8b-stheno-v3.2
    ```

### Running the Companion

```bash
python main.py
```

*(If using the Colab Bridge, start the respective Jupyter notebooks in `/colab_bridge` first, and update your `settings.json` with the generated tunneling URLs.)*

---

## 🎮 Commands

Inside the chat, you can use the following operational commands:

* `//help`: Show all commands.
* `//reset`: Clear the current conversation history.
* `//change_character`: Swap to a different profile (Glitch, Eira, Ria, etc.).
* `//show_settings`: View current app configuration.
* `//restart`: Cleanly reboot the application.

---

## 🛠️ Configuration

Edit `settings.json` to customize your experience:

* `remote_llm_url` / `remote_tts_url`: Set these to your Colab tunneling endpoints for cloud offloading.
* `tts_enabled`: Toggle voice entirely on/off.
* `speak_narration`: Choose if the Narrator should speak the actions or only text dialogue.
* `history_limit`: Control short-term memory limit (messages fed per prompt).
* `auto_recap_on_start`: Let the AI summarize the previous chat context upon booting.

---

## 📜 Roadmap

* [x] **Phase 1-3**: Core Terminal logic, Mood Engine, Persistent Memory, Profiles, and Relationships.
* [x] **Phase 4**: Cloud Computing (Colab Bridge), Voice & Response Streaming, Session Recaps, and Voice Cloning (XTTS v2).
* [ ] **Phase 5**: Visual Representation (GUI integration, Live2D, Lip Sync, active Character Expressions).
* [ ] **Speech-to-Text**: Full voice control for hands-free conversations.
* [ ] **Advanced Interactions**: Dynamic Scene Memory (Physical location/time tracking) and automated routines/actions.

---

## 🤝 Contributing

Feel free to fork, submit PRs, or suggest personalities.

*Disclaimer: This is an early build codebase. Expect some quirks.*
