# Implementation Plan - Recap Viewport Implementation

This plan outlines the steps to implement a "recap" feature that loads past conversation history into the terminal viewport.

## Phase 1: History Retrieval Enhancements [checkpoint: 6448035]

- [x] Task: Update `HistoryManager` in `engines/memory_v2.py` for flexible retrieval 7d04da7
    - [x] Write tests in `tests/test_memory_v2.py` for retrieving a specific number of recent messages
    - [x] Ensure `load_history(limit)` correctly returns the last `limit` messages from the history file
- [x] Task: Implement 24-hour priority check in `HistoryManager` 8494ca5
    - [x] Write tests for a method that checks if the last interaction was within 24 hours
    - [x] Implement `is_recent_interaction(profile_name, hours=24)` method
- [x] Task: Conductor - User Manual Verification 'History Retrieval Enhancements' (Protocol in workflow.md)

## Phase 2: Terminal Recap Integration [checkpoint: 0307b06]

- [x] Task: Integrate automatic recap into `main.py` startup 28c40a0
    - [x] Write tests for displaying 3-5 messages on startup (mocking `print`)
    - [x] Modify `main.py` to fetch the last 5 messages using `memory_manager.load_history(ch_name, limit=5)` before the input loop
    - [x] Implement a visual separator `=== Past Conversation ===` and header for the recap
- [x] Task: Implement `//history` command in `engines/app_commands.py` 18be2dc
    - [x] Write tests for the `//history` command execution and output
    - [x] Add `//history` and `//recap` to the `cmds` dictionary in `engines/app_commands.py`
    - [x] The command should fetch the last 15 messages and display them with the same styling as the automatic recap
- [x] Task: Conductor - User Manual Verification 'Terminal Recap Integration' (Protocol in workflow.md) 94c2589

## Phase 3: UI/UX Refinement [checkpoint: 4da3f74]

- [x] Task: Style the recap output for better readability 8313621
    - [x] Write tests for the recap styling (e.g., color usage)
    - [x] Use `Fore.LIGHTBLACK_EX` (dimmed) to display historical messages in the terminal
    - [x] Ensure the format clearly shows `Role: Message` (e.g., `Glitch: ...`)
- [x] Task: Conductor - User Manual Verification 'UI/UX Refinement' (Protocol in workflow.md)
