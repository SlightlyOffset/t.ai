# Specification: Improved Settings and Configuration Scope

## Overview
This track focuses on refining the configuration system by introducing global toggles for suppressing non-critical error messages and enabling/disabling Text-to-Speech (TTS) functionality. These settings will be persisted in `settings.json` and will be modifiable at runtime via new CLI commands.

## Functional Requirements
- **Global Settings Persistence**: Add `suppress_errors` and `enable_tts` fields to `settings.json`.
- **Error Suppression**: When `suppress_errors` is true, non-critical CLI errors (e.g., minor API timeouts, non-breaking logic warnings) should be caught and hidden from the user output.
- **TTS Toggle**: When `enable_tts` is false, the application must bypass all TTS processing logic to save resources and ensure silence.
- **Runtime CLI Commands**: Implement new commands to toggle these settings during an active session:
    - `/toggle tts`: Inverts the current state of `enable_tts` and saves it to `settings.json`.
    - `/toggle errors`: Inverts the current state of `suppress_errors` and saves it to `settings.json`.
- **User Feedback**: Provide immediate confirmation in the terminal when a setting is toggled (e.g., "TTS is now DISABLED").

## Non-Functional Requirements
- **Minimal Latency**: Toggling settings should not cause noticeable lag in the CLI.
- **Thread Safety**: Ensure that toggling `enable_tts` mid-sentence or mid-queue is handled gracefully (ideally stopping current speech).

## Acceptance Criteria
- [ ] `settings.json` contains `suppress_errors` and `enable_tts` with default values.
- [ ] Running `/toggle tts` updates the file and immediately affects TTS output.
- [ ] Running `/toggle errors` updates the file and hides non-critical error messages.
- [ ] All changes are verified with unit tests.

## Out of Scope
- Implementation of `log_level` granularity.
- Switching TTS engines (`edge-tts` vs `pyttsx3`) via command.
