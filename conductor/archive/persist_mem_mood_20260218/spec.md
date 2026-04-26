# Specification - Persistent Chat History and Mood Adjustment System

## Overview
This track implements a persistent chat history system and a dynamic mood adjustment system for the AI companion. The goal is to ensure that the AI's memory and emotional state are preserved across sessions, making the interaction feel more continuous and realistic.

## Requirements

### Persistent Chat History
- **Per-Profile History**: Chat history must be saved in JSON files specific to each character profile (e.g., `history/Glitch_history.json`).
- **Context Management**: Only the last 10-15 messages should be loaded into the active LLM context to maintain performance and stay within token limits.
- **Metadata**: History files should support metadata like timestamps and potentially mood states for future features.

### Mood Adjustment System
- **Relationship Meter**: A score ranging from -100 (Aggressive/Hostile) to +100 (Bestie/Affectionate).
- **Sentiment Analysis**: Triggers to adjust the mood score based on the user's input (nice words increase score, mean words or overuse decrease it).
- **Persistence**: The mood score must be saved in the character's JSON profile or a separate state file.
- **Mood Decay**: The score should slowly return toward 0 (Neutral) over time when the user is away.
- **Behavioral Logic**: The AI's behavior and tone (controlled via system prompts) should be tied to this score.

## Technical Design
- **Data Format**: JSON for both history and mood state.
- **Trigger Logic**: Simple keyword-based or sentiment-based triggers within the `responses.py` or a new `mood.py` engine.
- **Integration**: Update `main.py` and `engines/memory.py` to handle the new persistence logic.
