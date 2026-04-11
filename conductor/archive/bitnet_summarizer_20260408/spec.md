# Specification - BitNet Context Summarization

## Overview
Implement a context summarization feature that triggers when chat history exceeds a certain threshold (e.g., 15 messages). This uses a lightweight, 1-bit quantized model (BitNet) to condense older messages into a concise summary, preserving memory while minimizing VRAM usage.

## Functional Requirements
- **Threshold Detection**: Automatically trigger summarization when history length > 15 messages.
- **Lightweight Summarization**: Use a dedicated 1-bit model (e.g., `bitnet`) via Ollama to process the "old" history.
- **Hybrid Context**:
    - Summarize older history (all but the last 5 messages).
    - Keep the most recent 5 messages as raw text for immediate continuity.
- **Asynchronous Execution**: The summarization must run in a background worker to prevent the TUI from freezing on startup.
- **Visual Display**: The summary should be formatted distinctly in the chat log (e.g., [bold yellow] Memory Core Summary).

## Technical Requirements
- **Ollama Integration**: Call `ollama.generate` with a specific summarization prompt.
- **Error Handling**: Gracefully handle missing models or API failures by falling back to a "History too long to display" message.

## Acceptance Criteria
- [ ] History > 15 messages triggers the "Analyzing past memories..." system message.
- [ ] A concise summary appears in the chat log.
- [ ] The last 5 messages are displayed in full below the summary.
- [ ] The UI remains interactive while the summary is being generated.
