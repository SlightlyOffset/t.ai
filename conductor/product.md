# Initial Concept
A terminal-based, immersive AI companion with multi-voice TTS, deep character immersion, and a dynamic mood engine.

# Product Definition - AI Desktop Companion

## Vision
A lightweight, highly immersive AI companion that lives in the terminal. It features profile-dependent personalities, designed for roleplayers and AI enthusiasts who want characters that feel alive, remember the past, and have distinct, customizable behaviors.

## Target Audience
- Roleplayers and AI enthusiasts who prioritize immersion and unique, personality-driven interactions.

## Core Goals
- Provide a deeply immersive roleplaying experience with high-fidelity, distinct character voices for narration and dialogue.
- Deliver dynamic, profile-specific personalities that react uniquely to user interaction and history.
- Maintain a minimal system footprint while delivering complex emotional responses and relationship dynamics.

## Key Features
- **Zero-Latency Multi-Voice TTS**: Intelligent switching between narrator and character voices using multi-threaded queuing.
- **BitNet Context Summarization**: Automatically condenses long histories (>15 messages) using lightweight 1-bit models to preserve context without bloating VRAM.
- **Rolling Summarization & Memory Core Injection**: Automatically consolidates older chat history into a "Memory Core" that is injected into every AI interaction, ensuring long-term narrative recall without performance loss.
- **Seamless TUI Profile Management**: Non-blocking selection screen for companion and user profiles, with automated restoration of the last active session.
- **Dynamic Lorebook (World Info)**: Efficiently injects relevant world or character facts into the LLM context based on keywords detected in the recent conversation, enabling "infinite" world-building.
- **High-Fidelity Voice Cloning**: Integration of XTTS v2 for personalized character voices via local GPU or remote Colab bridge.
- **Relationship & Mood Engine**: A persistent -100 to +100 meter that dictates the AI's tone, obedience, and emotional state.
- **Profile-Dependent Personalities**: Customizable character profiles that dictate behavior, voice, and reaction styles.
- **Visual Representation**: High-fidelity character portraits integrated into the TUI using Sixel/Kitty protocols for deeper immersion.
- **High-Performance CLI**: Beautiful terminal rendering with dynamic colors and styles, optimized for minimal CPU/RAM usage.

## Future Roadmap
- **Dynamic Scene Memory**: Tracking location, time, and situational context for improved roleplay continuity.
