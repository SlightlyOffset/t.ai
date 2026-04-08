# Implementation Plan - Sidebar Toggle [checkpoint: baa8cd1]

## Phase 1: Binding & Logic
- [x] Define `BINDINGS` in `TaiMenu` to include the toggle key.
- [x] Implement an `action_toggle_sidebar` method.
- [x] Add a `show_sidebar` reactive property to `TaiMenu`.

## Phase 2: CSS & Layout Refactor
- [~] Update the Grid layout CSS to handle the missing column.
- [x] Ensure `#status_sidebar` has `display: none` or similar when hidden.

## Phase 3: Validation
- [x] Verify that chat history doesn't flicker during toggle.
- [x] Test with active streaming to ensure the AI bubble resizes correctly.
