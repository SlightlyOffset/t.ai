# Specification: Remote Semantic RAG (Optimized)

## Problem
The current Lorebook system is based on exact keyword matching. Standard RAG implementations require two network round-trips (1. Get Lore, 2. Get Chat), adding significant latency (300ms+).

## Solution: Single-Trip Internal RAG
Leverage the T4 GPU on Colab/Kaggle to perform vector retrieval **server-side** during the chat request. This eliminates the extra network round-trip.

### Architecture
1. **Sync Phase:** Upon connection, the TUI sends the entire `lorebook.json` to the `/sync_lore` endpoint.
2. **Indexing:** The bridge embeds all lore entries using `sentence-transformers` and stores them in an in-memory vector index (FAISS or simple Torch tensors).
3. **Optimized Request:** The TUI sends a normal chat request with a header or field: `"use_rag": true`.
4. **Server-Side Injection:**
    *   The Bridge receives the chat request.
    *   **Internal Step:** It embeds the user's latest message.
    *   **Internal Step:** It queries the local vector index for the Top 3 entries.
    *   **Internal Step:** It prepends these entries to the System Prompt automatically.
5. **Generation:** The LLM processes the enriched prompt and begins streaming immediately.

### Components
- **Local:** `engines/responses.py` simply toggles a flag; no longer needs to wait for a separate retrieval call.
- **Remote:** `Standalone LLM Bridge` becomes "Context-Aware," managing both retrieval and generation in a single pipeline.
