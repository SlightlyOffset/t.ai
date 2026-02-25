# AI Desktop Companion - TODO

## Phase 1: Foundation

- [x] Initialize Python environment and core dependencies (`colorama`, `ollama`, `edge-tts`)
- [x] Implement **TTS Module** with Edge Neural voices and `pyttsx3` fallback
- [x] Create Terminal-based **Profile Picker**
- [x] Build core `main.py` loop with character loading

## Phase 2: Personality & Logic

- [x] Build the **Mood Engine** (Weight-based obedience logic)
- [x] Create `engines/actions.py` with app dictionary (Browser, Notepad, etc.)
- [x] Integrate Ollama (Llama3) for actual AI intelligence
- [x] Implement **RP Screening** (Stripping `*narration*` from TTS)
- [x] Synchronize LLM responses with Mood Engine decisions (Hard-enforced obedience/refusal)

## Phase 3: Persistent Memory & Relationships

- [x] **Persistent Chat History**: Save/Load conversations to JSON per profile
- [x] **Context Window Management**: Feed last 10 messages back to the AI for short-term memory
- [x] **Global Settings System**: Integrate `settings.json` as the single source of truth
- [x] **Dynamic Mood Score**: Replace random rolls with a -100 to +100 relationship meter
- [x] **Sentiment Analysis**: Update mood based on user being "Nice" or "Mean"
- [x] **Connect Mood to Obedience**: Update `main.py` to use relationship score for decisions
- [x] **Relationship Awareness**: Add relationship tags to the prompt for context
- [x] **Mood Decay**: Implement logic for the AI to "calm down" over time

## Phase 3.5: Advanced RP & Immersion

- [x] **Profile Enrichment**: Add structured backstory and mannerisms to profile JSONs
- [x] **Enhanced Prompting**: Inject character-specific RP mannerisms and user info into system instructions
- [x] **Multi-Voice TTS**: Use separate voices for dialogue and narration
- [ ] **Dynamic Scene Memory**: Track current physical state/location in conversation
- [ ] **Mood-Locked RP**: Scale the intensity and descriptiveness of RP based on relationship score

## Phase 4: Features & Polishing

- [x] Response streaming and voice streaming
- [x] Implementing cloud computing for larger LLM e.g. 40B models
- [x] Implement recap or load history into terminal view
- [ ] Add more complex triggers (time, weather, or custom jokes)
- [ ] Implement background operation / system tray support
- [x] Source or record custom voice for **Voice Cloning (XTTS v2)**
- [x] Finalize error handling for offline/online transitions
- [ ] Implement Speech-to-Text (STT) for full voice control
- [ ] Integrate Chafa to display character portraits in a separate terminal window

## Phase 5: Visual Representation & Live2D

- [ ] Implement a GUI window for character display (PyQt6 or similar)
- [ ] **Character Expressions**: Map mood scores and sentiment to sprite changes (e.g., Happy, Neutral, Angry)
- [ ] **Live2D Integration**: Support Live2D models for high-fidelity animation
- [ ] **Lip-Sync**: Synchronize character mouth movements with TTS audio output
- [ ] **Idle Animations**: Implement breathing or blinking cycles for increased immersion
