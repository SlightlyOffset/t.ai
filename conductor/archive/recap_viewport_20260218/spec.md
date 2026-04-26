# Specification - Recap Viewport Implementation

## Overview
Implement a "recap" feature that loads past conversation history into the terminal viewport. This provides immediate context upon application start and allows users to manually retrieve more history during a session.

## Functional Requirements
- **Automatic Hybrid Display:** On profile load, the application will automatically display the last 3-5 messages from the saved history.
- **Visual Demarcation:** A clear visual separator (e.g., `=== Past Conversation ===`) will be used to separate historical messages from the current active session.
- **On-Demand Full Recap:** A new CLI command (e.g., `/history` or `/recap`) will be implemented to load a fuller history.
- **Recap Limits:** The full recap will load the last 15 messages, prioritizing those from the last 24 hours.
- **History Integration:** The system will utilize the existing `HistoryManager` (from `engines/memory_v2.py`) to fetch stored messages.

## Non-Functional Requirements
- **Startup Performance:** Loading the initial 3-5 messages must not cause a perceptible delay in the application's startup time.
- **Readability:** Historical messages should be formatted clearly to ensure they are easily distinguishable as past context.

## Acceptance Criteria
- [ ] Upon starting `main.py` with a profile, 3-5 past messages are printed followed by a separator.
- [ ] Historical messages appear before the "Ready" prompt.
- [ ] Typing `/history` in the terminal prints up to 15 messages from the profile's history file.
- [ ] The command correctly handles cases where fewer than 15 messages (or no messages) exist.

## Out of Scope
- Searching within history.
- Paginating history (e.g., "Page 2").
- Modifying or deleting individual historical messages via the CLI.
