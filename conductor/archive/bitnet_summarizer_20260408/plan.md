# Implementation Plan - BitNet Context Summarization

## Phase 1: Engine Preparation
- [x] Create a `generate_summary` helper in `engines/responses.py` (or locally in `menu.py`) that interfaces with Ollama. (90cac64)
- [x] Define the summarization prompt (concise bullet points, mood tracking). (ee1ca2b)

## Phase 2: Recap Logic Refactor
- [x] Update `run_recap` in `menu.py` to handle the history split (older messages vs. recent 5). (d68ce72)
- [x] Wrap the summarization call in a `@work(thread=True)` worker. (d68ce72)
- [x] Use `app.call_from_thread` to update the chat log with the results. (d68ce72)

## Phase 3: Visual Polish
- [x] Apply specific styling to the "Memory Core" readout. (804fcca)
- [x] Add a "Summarization in progress..." spinner or status label if possible. (804fcca)

## Phase 4: Validation
- [x] Test with a profile containing 50+ messages. (de3c0b7)
- [x] Verify that the summary is coherent and useful for the AI's current context. (de3c0b7)
