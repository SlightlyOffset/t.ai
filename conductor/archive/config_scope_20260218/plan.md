# Implementation Plan: Improved Settings and Configuration Scope

This plan outlines the steps to introduce `suppress_errors` and `enable_tts` settings, including persistence in `settings.json` and runtime toggling via CLI commands, following a TDD approach.

## Phase 1: Configuration Schema and Persistence
Focuses on updating the configuration management system to support the new settings.

- [ ] Task: Update `settings.json` and `engines/config.py` for new settings
    - [ ] Write unit tests in `tests/test_config.py` to verify `suppress_errors` and `enable_tts` can be loaded, saved, and have sensible defaults.
    - [ ] Update `settings.json` with default values: `{"suppress_errors": false, "enable_tts": true}`.
    - [ ] Modify `engines/config.py` (or the relevant config handler) to expose these new settings and provide a method to update them programmatically.
- [ ] Task: Conductor - User Manual Verification 'Phase 1: Configuration Schema and Persistence' (Protocol in workflow.md)

## Phase 2: Core Logic Integration
Integrates the new settings into the error handling and TTS modules.

- [ ] Task: Implement Error Suppression Logic
    - [ ] Write unit tests to verify that "non-critical" errors are suppressed when `suppress_errors` is enabled.
    - [ ] Refactor error handling (likely in `engines/utilities.py` or `main.py`) to respect the `suppress_errors` flag.
- [ ] Task: Implement TTS Toggle Logic
    - [ ] Write unit tests in `tests/test_tts_module.py` to verify that TTS requests are bypassed when `enable_tts` is disabled.
    - [ ] Modify `engines/tts_module.py` to check the `enable_tts` flag before processing speech queues.
- [ ] Task: Conductor - User Manual Verification 'Phase 2: Core Logic Integration' (Protocol in workflow.md)

## Phase 3: Runtime CLI Commands
Adds the user interface for toggling settings during a session.

- [ ] Task: Implement Toggle Commands
    - [ ] Write unit tests in `tests/test_app_commands.py` for `/toggle tts` and `/toggle errors`.
    - [ ] Implement the command logic in `engines/app_commands.py` to update the global config and provide user feedback.
    - [ ] Ensure the configuration is saved to `settings.json` immediately upon toggle.
- [ ] Task: Conductor - User Manual Verification 'Phase 3: Runtime CLI Commands' (Protocol in workflow.md)

## Phase 4: Final System Verification
Ensures all components work together seamlessly.

- [ ] Task: End-to-End Verification
    - [ ] Perform a manual walkthrough of toggling both settings and verifying their impact on the system.
    - [ ] Ensure that toggling TTS mid-execution (if applicable) is handled gracefully.
- [ ] Task: Conductor - User Manual Verification 'Phase 4: Final System Verification' (Protocol in workflow.md)
