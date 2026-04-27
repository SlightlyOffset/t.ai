# Specification - Sidebar Toggle Implementation

## Overview
Add a user-friendly way to toggle the visibility of the character status sidebar. This allows for a more immersive "full-screen" chat experience when stats are not needed.

## Functional Requirements
- **Toggle Binding**: Use a standard keybinding (e.g., `Ctrl+B`) to toggle visibility.
- **Dynamic Layout**: When hidden, the chat container should expand to fill the entire application width.
- **Persistence**: (Optional) Remember the toggle state across application restarts.

## Technical Requirements
- **Textual Reactive State**: Use a reactive boolean (e.g., `show_sidebar`) to trigger the TUI refresh.
- **CSS Transitions**: Utilize Textual's `.display` or `.width` properties to animate or jump the sidebar in and out.

## Acceptance Criteria
- [ ] Pressing the toggle key hides the sidebar immediately.
- [ ] Pressing it again restores the sidebar at its original width.
- [ ] The chat history correctly wraps and resizes when the sidebar is toggled.
