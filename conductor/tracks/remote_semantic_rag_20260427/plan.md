# Implementation Plan: Remote Semantic RAG (Optimized)

## Phase 1: Bridge Server Enhancements
- [ ] Add `sentence-transformers` and `torch` to bridge requirements.
- [ ] Implement `LoreManager` class to handle vector storage and cosine similarity on GPU.
- [ ] Add `/sync_lore` (POST) endpoint to ingest `lorebook.json`.
- [ ] **Crucial:** Modify the `/chat` endpoint to perform internal retrieval and prompt injection before calling the LLM.

## Phase 2: Local Client Integration
- [ ] Update `engines/lorebook.py` to handle the one-time sync at startup.
- [ ] Modify `engines/responses.py` to send the `use_rag` flag in the JSON payload.
- [ ] Ensure the local TUI doesn't block while the bridge is "thinking" about retrieval.

## Phase 3: Validation
- [ ] Verify that retrieved lore is actually present in the LLM context (debug logs).
- [ ] Benchmark "Single-Trip" vs "Standard" chat latency.
