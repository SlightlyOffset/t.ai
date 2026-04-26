# Implementation Plan: Hybrid Offloading & Async Post-Processing

## Phase 1: Configuration
- [x] Add `local_utility_model` to `engines/config.py` with a default (e.g., `"llama3.2"` or `"phi3"`).
- [x] Ensure `settings.json` can store and override this value.

## Phase 2: Reroute Utility Tasks
- [x] Modify `get_sentiment_score` in `engines/responses.py` to:
    - Ignore `remote_url`.
    - Use `local_utility_model`.
    - Always call local Ollama.
- [x] Modify `generate_summary` and `update_rolling_summary` in `engines/responses.py` to:
    - Ignore `remote_url`.
    - Use `local_utility_model`.
    - Always call local Ollama.

## Phase 3: Asynchronous Post-Processing
- [x] Refactor `get_respond_stream` in `engines/responses.py` to:
    - Move sentiment scoring, profile score updates, and narrative state updates into a background thread.
    - Use `threading.Thread` to "fire and forget" these tasks after the main response stream has finished yielding all chunks.
- [x] Verify that UI unblocks immediately after the text is fully displayed.

## Phase 4: Validation
- [ ] Test with Colab bridge enabled.
- [x] Verify sentiment scores are still correctly calculated and saved.
- [x] Monitor Colab logs to ensure utility tasks are no longer hitting the remote GPU.
