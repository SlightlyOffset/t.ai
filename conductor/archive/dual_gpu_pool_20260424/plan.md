# Implementation Plan: Dual-Worker GPU Pool

## Phase 1: Notebook Architecture Shift
- [x] Remove `device_map=\"balanced\"`. [b614891]
- [x] Load `Model A` and `Tokenizer A` onto `cuda:0`. [b614891]
- [x] Load `Model B` and `Tokenizer B` onto `cuda:1`. [b614891]
- [x] Update diagnostic printouts to show allocation for both independent models. [b614891]

## Phase 2: FastAPI Dispatcher
- [x] Implement a worker queue or threading mechanism to track which GPU is busy. [d387d28]
- [x] **Stream Router:** Route incoming stream requests to the first free GPU. [d387d28]
- [x] **Batch Splitter:** When a request with `n > 1` arrives, split it. For example, assign `n=1` task to GPU 0 and another `n=1` task to GPU 1 in parallel until all `n` candidates are generated. [d387d28]
- [x] Ensure strict locking per-GPU so a single GPU is never tasked with concurrent generations. [d387d28]

## Phase 3: Validation
- [x] Test with `n=4` from the local app and verify the bridge handles it without crashing.
- [x] Verify stream requests during background reranking still process smoothly.
