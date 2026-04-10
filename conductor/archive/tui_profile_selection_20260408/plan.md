# Implementation Plan - TUI Profile Selection

## Phase 1: Startup Refactoring [checkpoint: 7149f8c]
- [x] Remove `pick_profile` and `pick_user_profile` from the `__main__` block in `menu.py`. d390df1
- [x] Update `TaiMenu.on_mount` to attempt loading profiles from `settings.json`. 4dbc7a7
- [x] If loading fails, push the `ProfileSelectScreen` immediately. d2c7021

## Phase 2: ProfileSelectScreen Implementation [checkpoint: cb985e6]
- [x] Review and integrate existing `ProfileSelectScreen.py` into the `menu.py` structure (or import it properly). cb985e6
- [x] Implement a `ListView` or `OptionList` to display available `.json` files from the `profiles/` directory. cb985e6
- [x] Add event handlers to capture the user's selection. cb985e6

## Phase 3: Integration and Callbacks [checkpoint: 348dc82]
- [x] Add a `ctrl+o` binding to open the selection screen. 348dc82
- [x] Implement a callback or message handler to process the selected profile from the screen. 348dc82
- [x] Create a `switch_profile(char_path)` method in `TaiMenu` to handle resetting the chat, updating settings, and running the recap. 348dc82


## Phase 4: Validation
- [x] Test cold boot (no settings) vs warm boot (existing settings).
- [x] Test switching profiles mid-conversation to ensure memory and TTS queues are handled cleanly.
