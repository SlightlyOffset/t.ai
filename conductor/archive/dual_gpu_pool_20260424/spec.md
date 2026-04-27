# Specification: Dual-Worker GPU Pool Architecture

## Objective
Convert the remote LLM bridge (Colab/Kaggle) from a balanced layer-split architecture to a true Dual-Worker Pool. This involves loading two complete, independent copies of the model (one on each T4 GPU) and routing traffic between them.

## Core Mechanisms
1.  **Independent Loading:** 
    - `Model A` loaded strictly on `device: 0`.
    - `Model B` loaded strictly on `device: 1`.
2.  **Request Router:**
    - The FastAPI server acts as a dispatcher.
    - Streams (n=1) grab the first available GPU.
    - Batches (n>1) are split. (e.g., `n=4` is executed as two parallel `n=2` tasks, or four `n=1` tasks sequentially across both GPUs).
3.  **Strict KV Cache Limits:**
    - By isolating the work per GPU to `n=1` or `n=2`, the VRAM spike caused by the KV cache is mathematically bound, completely preventing OOMs.

## Benefits
*   **100% GPU Utilization:** Both Kaggle GPUs process different candidates simultaneously.
*   **OOM Immunity:** Eliminates the concurrent VRAM spikes caused by multi-sequence generation on a single model instance.
*   **Double Throughput:** Generates batches in roughly half the time compared to sequential generation.
