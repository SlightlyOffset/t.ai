# Specification: XTTS Cache De-sync Fix

## Problem
When using the remote XTTS bridge, the client maintains a local in-memory cache (`_UPLOADED_VOICES`) of speaker profiles it has already uploaded to the server. If the server restarts, or if the client switches to a profile that is incorrectly perceived as already "synced," the server returns a 404 error during generation. The client currently treats this 404 as a fatal error and falls back to `edge-tts`.

## Goal
Implement an automatic recovery mechanism that detects 404 errors from the remote bridge, invalidates the local stale cache, and re-uploads the speaker profile seamlessly.

## Requirements
- **Error Detection**: Catch `404 Not Found` responses from the `/generate_tts` endpoint.
- **Cache Invalidation**: Remove the problematic `speaker_id` from the local `_UPLOADED_VOICES` set.
- **Auto-Retry**: Automatically trigger a recursive call to `generate_remote_xtts` after cache invalidation to ensure the voice is uploaded and audio is generated without user intervention.
- **Logging**: Provide clear console feedback in debug mode when a de-sync is detected.
