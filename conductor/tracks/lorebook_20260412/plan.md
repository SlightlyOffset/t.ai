# Implementation Plan: Lorebook (World Info)

## Objective
Build and integrate a scalable Lorebook system that injects dynamic context into the LLM stream based on conversational keyword triggers.

## Key Files & Context
- `engines/lorebook.py` (New File)
- `engines/responses.py` (Modified)
- `engines/app_commands.py` (Modified - optional command implementation)
- `lorebooks/default.json` (New Directory/File)

## Implementation Steps

1. [x] **Create the Lorebook Data Engine (`engines/lorebook.py`)** [5e08b4d]
   - Implement `load_lorebook(filepath)` to safely read and parse `lorebooks/default.json`.
   - Implement `scan_for_lore(recent_messages, lorebook_data)` to iterate over recent history and find matching keywords via whole-word Regex (`\bword\b`).
   - Format the matched entries into a structured `[WORLD INFO / LORE]` string block, respecting the `insertion_order` property.

2. [x] **Integrate Scanner into Prompt Context (`engines/responses.py`)** [249d1ed]
   - In `get_respond_stream`, load the lorebook data (could be cached per session).
   - Pass the last `N` messages to `scan_for_lore()`.
   - Take the resulting lore text and prepend/append it to `system_extra_info` alongside the `Memory Core` and `CURRENT SCENE`.

3. [x] **Implement Basic Command Hooks (`engines/app_commands.py`)** [df8bacf]
   - Add a basic `//lore reload` command to hot-reload the `lorebook.json` from disk.
   - (Optional) Add `//lore add [keys] | [content]` for quick runtime additions.

4. [x] **Initialize Default Data** [c1c9c03]
   - Create a `lorebooks` directory at the project root.
   - Add a sample `default.json` demonstrating the format.

## Verification & Testing
- **Unit Tests:** Verify `scan_for_lore` correctly matches whole words and ignores partial matches (e.g., "elf" should not match "himself").
- **Integration Test:** Mock a chat history and ensure the generated `system_extra_info` string contains the correct lorebook blocks.
- **Manual TUI Test:** Type a keyword in the app, confirm the LLM integrates the context seamlessly in its generated reply without hallucinating.