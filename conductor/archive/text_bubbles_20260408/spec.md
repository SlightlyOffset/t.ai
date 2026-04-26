# Specification - Text Bubble UI Implementation

## Overview
Transform the current plain-text chat interface in `menu.py` (t.ai) into a modern, visually distinct "bubble" style. This enhances immersion by clearly separating user messages from AI responses through alignment, colors, and borders.

## Functional Requirements
- **Bubble Alignment**:
    - **User Messages**: Aligned to the **right** side of the chat area.
    - **Companion Messages**: Aligned to the **left** side.
- **Visual Distinction**:
    - Distinct background colors for User vs. Companion bubbles (e.g., $accent vs $panel).
    - Rounded borders or styled borders to represent a "bubble" shape.
- **Content Formatting**:
    - Maintain existing rich text support (italics for narration).
    - Dynamic bubble sizing (width should wrap based on content).

## Non-Functional Requirements
- **Performance**: Bubble rendering should not cause flickering during LLM streaming.
- **Responsiveness**: Bubbles must resize correctly when the terminal window is adjusted.

## Acceptance Criteria
- [ ] User messages appear on the right with a specific border/color.
- [ ] AI messages appear on the left with a specific border/color.
- [ ] AI messages update in real-time within their bubble during streaming.
- [ ] All narration (*) is correctly italicized within the bubbles.
