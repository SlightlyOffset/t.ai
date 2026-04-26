# Specification: Lorebook (World Info)

## Objective
Implement a Lorebook (World Info) system that efficiently injects relevant world/character facts into the LLM context based on keywords detected in the recent conversation history. This solves context limits while enriching the "infinite" world building for the AI companion.

## Features
1. **Lorebook JSON Structure:** A centralized or profile-specific JSON file (`lorebooks/default.json` or similar) holding an array of entries with keys, content, and an enabled flag.
2. **Context Scanner:** A module (`engines/lorebook.py`) that scans the most recent messages (e.g., last 3) for keywords (using word-boundary regex) defined in the lorebook entries.
3. **Prompt Injection:** Append the matched lore entries dynamically into the `system_extra_info` block within `get_respond_stream` just before the LLM call.
4. **Command Interface (Optional):** Introduce an app command (e.g., `//lore`) to query or manage lore during a session.

## Data Structures
```json
{
  "entries": [
    {
      "id": "1",
      "keys": ["tavern", "inn"],
      "content": "The tavern is a cozy place.",
      "enabled": true,
      "insertion_order": 50
    }
  ]
}
```