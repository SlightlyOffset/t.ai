# Implementation Plan - TUI Profile Selection

## Phase 1: Startup Refactoring [checkpoint: 7149f8c]
- [x] Remove `pick_profile` and `pick_user_profile` from the `__main__` block in `menu.py`. d390df1
- [x] Update `TaiMenu.on_mount` to attempt loading profiles from `settings.json`. 4dbc7a7
- [x] If loading fails, push the `ProfileSelectScreen` immediately. d2c7021

## Phase 2: ProfileSelectScreen Implementation
- [ ] Review and integrate existing `ProfileSelectScreen.py` into the `menu.py` structure (or import it properly).
- [ ] Implement a `ListView` or `OptionList` to display available `.json` files from the `profiles/` directory.
- [ ] Add event handlers to capture the user's selection.

## Phase 3: Profile Switching Logic
- [ ] Add a `ctrl+p` binding to open the selection screen.
- [ ] Implement a callback or message handler to process the selected profile from the screen.
- [ ] Create a `switch_profile(char_path)` method in `TaiMenu` to handle resetting the chat, updating settings, and running the recap.

## Phase 4: Validation
- [ ] Test cold boot (no settings) vs warm boot (existing settings).
- [ ] Test switching profiles mid-conversation to ensure memory and TTS queues are handled cleanly.
