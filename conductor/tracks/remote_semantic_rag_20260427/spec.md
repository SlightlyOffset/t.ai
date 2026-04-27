# Specification: Remote Semantic RAG

## Problem
The current Lorebook system is based on exact keyword matching. It fails if the user uses synonyms or slightly different phrasing. Local RAG (on the user's CPU) is slow and adds dependency overhead to the TUI.

## Solution
Leverage the T4 GPU on Colab/Kaggle to perform vector embeddings and similarity search.

### Architecture
1. **Sync Phase:** Upon connection, the TUI sends the entire `lorebook.json` to a new `/sync_lore` endpoint on the bridge.
2. **Indexing:** The bridge uses `sentence-transformers` (on GPU) to embed all lore entries.
3. **Retrieval Phase:** Before generating a response, the TUI sends the last 3 messages to a `/query_lore` endpoint.
4. **Injection:** The bridge returns the top 3 most relevant entries. The TUI injects these into the system prompt.

### Components
- **Local:** `engines/lorebook.py` needs a new `RemoteLoreClient`.
- **Remote:** `Standalone LLM Bridge` needs an embedding model (e.g., `all-MiniLM-L6-v2`) and a simple in-memory vector search.
