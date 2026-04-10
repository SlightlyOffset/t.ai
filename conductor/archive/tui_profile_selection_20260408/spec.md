# Specification - TUI Profile Selection

## Overview
Replace the blocking terminal prompts (`input()`) used for profile selection on startup with a seamless, immersive TUI experience. The application should automatically load the last active companion and user profiles upon launch. A dedicated `ProfileSelectScreen` will allow users to switch characters from within the TUI.

## Functional Requirements
- **Automatic Startup**: On launch, read `current_character_profile` and `current_user_profile` from `settings.json`. If valid, load them immediately.
- **Fallback Startup**: If no valid profiles are found in settings (e.g., first run), automatically push the `ProfileSelectScreen`.
- **TUI Selection Screen**:
    - Display a list of available character profiles (`.json` files in the `profiles/` directory).
    - Provide an option to select a user profile (or default to a standard user if none are selected).
- **Navigation**:
    - Add a hotkey (e.g., `Ctrl+P`) to open the `ProfileSelectScreen` from the main chat.
    - Support exiting the screen without changing the profile.
- **Profile Switching Logic**: When a new profile is selected:
    - Update `settings.json`.
    - Clear the current chat log.
    - Load the new profile data, update the sidebar, and trigger the history recap.

## Technical Requirements
- **Textual Screens**: Utilize Textual's `Screen` and `App.push_screen()` / `App.pop_screen()` mechanics.
- **Remove Blocking Calls**: Eliminate `pick_profile()` and `pick_user_profile()` from the `__main__` execution block.

## Acceptance Criteria
- [ ] App launches directly into the chat interface using the last active profile.
- [ ] Pressing `Ctrl+P` opens the profile selection screen.
- [ ] Selecting a new profile updates the chat interface, sidebar, and history without restarting the app.
- [ ] The terminal is never blocked by standard input prompts.
