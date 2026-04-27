# Specification - Dedicated Command Mode

## Overview
Move the operational `//` system commands out of the main conversational chat input to prevent accidental sending to the AI. Introduce a dedicated "Command Mode" input (e.g., via a popup or toggle) triggered by a specific hotkey (`Ctrl+!`).

## Functional Requirements
- **Keybinding**: A hotkey (e.g., `Ctrl+!`) triggers Command Mode.
- **Dedicated Input**: A separate input field or a `ModalScreen` appears, focused specifically on system commands.
- **Input Separation**: 
  - The main chat input should no longer process or intercept strings starting with `//`. Anything typed there goes straight to the LLM.
  - The command input only processes system commands (like `reset`, `show_settings`, `change_character`).
- **Feedback**: Success or failure of a command must display a system message in the chat log (e.g., `[System] History cleared.`).

## Technical Requirements
- Create a Textual `ModalScreen` for the command input or toggle the main input's behavior dynamically.
- Update `menu.py` bindings and input handling.

## Acceptance Criteria
- [ ] Pressing `Ctrl+!` opens a command input.
- [ ] Submitting a command successfully updates the app state/settings.
- [ ] Typing `//reset` in the main chat sends the text literally to the AI.
