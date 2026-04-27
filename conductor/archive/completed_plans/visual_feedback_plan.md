# Visual Feedback for Regeneration Plan

## Objective
Add visual feedback when a user triggers a regeneration of an AI message. The AI message bubble will slide to the side and fade slightly to indicate that a new response is being generated.

## Key Files & Context
- **`tcss/menu.tcss`**: The stylesheet for the Textual UI. Needs a transition property on `.ai_bubble` and a new `.regenerating` class to handle the slide and fade effects.
- **`menu.py`**: The main UI code. Needs to apply the `.regenerating` class and update the text when regeneration is requested, and then remove the class when the new stream starts.

## Implementation Steps

1.  **Update CSS (`tcss/menu.tcss`)**
    -   Add `transition: offset 300ms in_out_cubic, opacity 300ms in_out_cubic;` to `.ai_bubble`.
    -   Create a new class `.regenerating` with `offset-x: 10;` (to slide it right) and `opacity: 0.5;` (to fade it).

2.  **Update Regeneration Logic (`menu.py` - `action_next_or_regenerate_response`)**
    -   When regeneration is triggered (the `else` block), find the last `.ai_bubble`.
    -   Update its text to show a temporary loading message (e.g., `[dim italic]Regenerating response...[/dim italic]`).
    -   Add the `regenerating` CSS class to the bubble using `ai_bubble.add_class("regenerating")`.

3.  **Update Stream Logic (`menu.py` - `stream_response`)**
    -   In `stream_response`, if `is_regeneration` is `True`, remove the `regenerating` class from the bubble using `self.app.call_from_thread(ai_msg.remove_class, "regenerating")` so it slides back into place as the new text starts streaming.

## Verification & Testing
-   Trigger regeneration (`Alt+Right` at the latest message or `//regen`).
-   Observe the last AI bubble updating its text, fading slightly, and sliding 10 cells to the right.
-   Once the LLM starts streaming the new response, the bubble should slide back to its original position, become fully opaque, and display the new text.