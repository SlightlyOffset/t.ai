# Implementation Plan: XTTS Cache De-sync Fix

## Phase 1: Engine Modification
- [x] Update `engines/xtts_remote.py` to handle 404 responses in `generate_remote_xtts`.
- [x] Implement local cache (`_UPLOADED_VOICES`) invalidation logic.
- [x] Implement recursive auto-retry mechanism.

## Phase 2: Verification
- [ ] Manually simulate a server-side cache wipe.
- [ ] Verify that switching profiles re-registers the voice on the bridge.
- [ ] Verify no infinite loops occur if the server is permanently broken (ensure recursion only happens once).
