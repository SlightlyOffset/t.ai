# Implementation Plan - Dedicated Command Mode

## Phase 1: Modal Screen Design
- [ ] Create a `CommandModal(ModalScreen)` class in `menu.py` containing an `Input` widget.
- [ ] Add basic CSS to center the modal over the main interface.

## Phase 2: Action Binding
- [ ] Add the `Ctrl+!` (or `ctrl+1`) keybinding to `TaiMenu` bindings.
- [ ] Implement `action_open_command_palette` to push the `CommandModal` to the screen stack.

## Phase 3: Logic Separation
- [ ] Remove the `if message.startswith("//")` logic from `on_input_submitted` (the main chat input).
- [ ] Wire the `CommandModal`'s submit event to the existing `app_commands()` parser.
- [ ] Pass results back to `TaiMenu` to print success/failure messages and pop the modal screen.

## Phase 4: Validation
- [ ] Send `//test` in main chat and ensure the AI responds.
- [ ] Open command mode, type `reset`, and ensure the chat history clears.
