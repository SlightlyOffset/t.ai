# Implementation Plan: Remote Semantic RAG

## Phase 1: Bridge Server Enhancements
- [ ] Add `sentence-transformers` to bridge requirements.
- [ ] Implement `LoreManager` class on the bridge to handle GPU-accelerated embeddings.
- [ ] Add `/sync_lore` (POST) and `/query_lore` (POST) endpoints to the FastAPI app.

## Phase 2: Local Client Integration
- [ ] Update `engines/lorebook.py` to support remote syncing.
- [ ] Modify `engines/responses.py` to call `/query_lore` before the main LLM call.
- [ ] Add fallback to keyword matching if the remote bridge is unavailable.

## Phase 3: Validation
- [ ] Test with complex world info triggers.
- [ ] Measure latency impact (aim for < 200ms for retrieval).
