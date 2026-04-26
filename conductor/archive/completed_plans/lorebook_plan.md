# Lorebook (World Info) Implementation Plan

## Objective
Build and integrate a scalable Lorebook system that injects dynamic context into the LLM stream based on conversational keyword triggers, preventing context bloat while enabling rich world-building.

## Key Files & Context
- `engines/lorebook.py` (New File)
- `engines/responses.py` (Modified)
- `engines/app_commands.py` (Modified)
- `lorebooks/default.json` (New File/Directory)

## Proposed Solution
We will implement a lightweight, regex-based keyword scanner that runs just before LLM generation. When a keyword is found in the recent history, its corresponding lore is appended to the `system_extra_info` context. 

## Implementation Steps
1. **Create the Lorebook Data Engine (`engines/lorebook.py`)**
   - Implement `load_lorebook(filepath)` to safely read and parse `lorebooks/default.json`.
   - Implement `scan_for_lore(recent_messages, lorebook_data)` to iterate over recent history and find matching keywords via whole-word Regex (`\bword\b`).
   - Format the matched entries into a structured `[WORLD INFO / LORE]` string block, respecting the `insertion_order` property.

2. **Integrate Scanner into Prompt Context (`engines/responses.py`)**
   - In `get_respond_stream`, load the lorebook data (or use a cached version).
   - Pass the last 3-5 messages to `scan_for_lore()`.
   - Take the resulting lore text and prepend/append it to `system_extra_info` alongside the `Memory Core` and `CURRENT SCENE`.

3. **Implement Basic Command Hooks (`engines/app_commands.py`)**
   - Add a `//lore reload` command to hot-reload the `lorebook.json` from disk during an active session.

4. **Initialize Default Data**
   - Create a `lorebooks` directory at the project root.
   - Add a sample `default.json` demonstrating the format (e.g., tavern, character relationships).

## Verification & Testing
- **Unit Tests:** Verify `scan_for_lore` correctly matches whole words and ignores partial matches (e.g., "elf" vs "himself").
- **Integration Test:** Mock a chat history and ensure the generated `system_extra_info` string contains the correct lorebook blocks.
- **Manual TUI Test:** Type a keyword in the app, confirm the LLM integrates the context seamlessly in its generated reply without hallucinating.