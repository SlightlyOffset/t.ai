# Swipe-to-Regenerate AI Message Feature Plan

## Objective
Implement a swipe-like navigation for AI responses where all responses for the last user message are kept. 
- `Alt+Right`: Moves to the next response. If at the latest response, it regenerates a new one.
- `Alt+Left`: Scrolls back to previous responses for the same user prompt.

## Key Files & Context
- **`engines/responses.py`**: Manages LLM requests and persistent history saving.
- **`menu.py`**: The TUI code. Needs new bindings (`Alt+Left`/`Alt+Right`), logic to swap rendered text, and UI indicators like `[< 2/3 >]`.
- **`engines/memory_v2.py`**: Handles persistent memory. We will adapt history loading to handle "alternatives" gracefully without changing core architecture.

## Implementation Steps

1.  **Data Structure Update for History**
    -   When regenerating, we update the last `assistant` message in the JSON history to include `alternatives` (a list of strings) and `selected_index` (an integer).
    -   Example: `{"role": "assistant", "content": "selected_response", "alternatives": ["resp1", "resp2"], "selected_index": 1}`.

2.  **Modify `engines/responses.py` (`get_respond_stream`)**
    -   Add an optional `is_regeneration: bool = False` flag to `get_respond_stream`.
    -   If `is_regeneration=True`:
        -   Load the history. Pop the last `assistant` message to exclude it from the LLM prompt context (so it doesn't see its own rejected response).
        -   Do not append `user_input` to the end of the `messages` array, as it's already the last message in `history`.
        -   When saving to `memory_manager`:
            -   Instead of appending a new user + assistant pair, mutate the last assistant message.
            -   Initialize `"alternatives": [last_content]` if it doesn't exist.
            -   Append `reply` to `"alternatives"`.
            -   Set `"selected_index"` to `len(alternatives) - 1`.
            -   Set `"content"` to `reply`.

3.  **Add Key Bindings in `menu.py`**
    -   Add to `TaiMenu.BINDINGS`:
        -   `("alt+left", "previous_response", "Previous Response")`
        -   `("alt+right", "next_or_regenerate_response", "Next/Regenerate Response")`

4.  **Implement `TaiMenu` Actions**
    -   `action_previous_response`:
        -   Load full history. Find the last `assistant` message.
        -   If `"alternatives"` exists and `selected_index > 0`:
            -   Decrement `selected_index`.
            -   Update `"content"` to `alternatives[selected_index]`.
            -   Save history.
            -   Call a helper `refresh_last_ai_message()` to update the UI text of the last `.ai_bubble` to show the old text + `[< {index+1}/{total} >]`.
    -   `action_next_or_regenerate_response`:
        -   Load full history. Find the last `assistant` message.
        -   If `"alternatives"` exists and `selected_index < len(alternatives) - 1`:
            -   Increment `selected_index`.
            -   Update `"content"` to `alternatives[selected_index]`.
            -   Save history.
            -   Call `refresh_last_ai_message()` to update UI.
        -   Else (we are at the latest response):
            -   Extract the user message text that preceded this assistant message.
            -   Trigger `self.stream_response(user_text, is_regeneration=True)`.

5.  **UI Updates (`menu.py`)**
    -   Update `stream_response` to accept `is_regeneration`.
    -   If `is_regeneration=True`, instead of mounting a new `.ai_row`, update the existing last `.ai_bubble` and stream the new text into it, ensuring the pagination indicator `[< {index}/{total} >]` updates correctly at the end.
    -   Update `add_message` and recap logic (`run_recap`) to visually append the `[< 1/2 >]` indicator if `alternatives` are present in `msg_data`.

## Verification & Testing
-   Press `Alt+Right` after an AI response: verifies regeneration begins, replacing the current bubble, and updates the history JSON with an `alternatives` array.
-   Press `Alt+Left`: verifies the UI reverts to the first response, displaying `[< 1/2 >]`, and history is saved with `selected_index=0`.
-   Press `Alt+Right` again: verifies it swaps back to `[< 2/2 >]` without triggering a new generation.
-   Restart app: verifies `run_recap` loads the currently `selected_index` and displays the correct alternative with its indicator.