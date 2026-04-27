# Implementation Plan - Text Bubble UI Implementation [checkpoint: 22844f0]

## Phase 1: CSS Foundation
- [x] Define `.user_bubble` and `.ai_bubble` classes in `menu.py` CSS.
- [x] Set `align: right` and `align: left` for the respective classes.
- [x] Apply border, padding, and background color styling.

## Phase 2: Widget Refactoring
- [x] Update `add_message` to wrap the `Static` message in a container for alignment.
- [x] Update `stream_response` to mount the AI bubble container.

## Phase 3: Streaming Compatibility
- [x] Ensure the streaming update `ai_msg.update()` correctly targets the inner `Static` widget without breaking the bubble container.

## Phase 4: Validation
- [x] Verify alignment on different terminal widths.
- [x] Test with long multiline responses and RP narration.
