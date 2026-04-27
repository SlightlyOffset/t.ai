# Refactor Main Entry Point with Environment Setup

**Objective:**
Rename the deprecated `main.py` (CLI version) to `legacy_main.py` and create a robust new `main.py` that serves as the primary launcher for the Textual UI (`menu.py`). The new launcher will perform essential dependency checks and environment setup to ensure the app runs smoothly.

**Key Files & Context:**
*   `main.py`: Current CLI entry point (to be renamed).
*   `menu.py`: The Textual UI application.
*   `requirements.txt` (or known dependencies): Need to ensure libraries like `textual`, `ollama`, `edge-tts`, and `colorama` are available.

**Implementation Steps:**

1.  **Preserve Legacy Code:**
    *   Rename the existing `main.py` to `legacy_main.py` so the old CLI logic remains available for reference.

2.  **Create the New Entry Point (`main.py`):**
    *   **Python Version Check:** Ensure the user is running Python 3.10+ (or the required version).
    *   **Directory Setup:** Automatically create necessary folders if they don't exist:
        *   `profiles/`
        *   `user_profiles/`
        *   `history/`
        *   `img/`
        *   `cache/`
        *   `voices/`
    *   **Dependency Check:** Implement a `try/except` block attempting to import core third-party libraries (`textual`, `ollama`, `requests`, `colorama`, `edge_tts`). If an `ImportError` occurs, halt execution gracefully with a helpful message (e.g., "Please run `pip install -r requirements.txt`").
    *   **Launch App:** If all checks pass, import `TaiMenu` and `set_terminal_appearance` from `menu.py`, and invoke `app.run()`.

3.  **Clean Up `menu.py`:**
    *   Remove or simplify the `if __name__ == "__main__":` block at the bottom of `menu.py` since `main.py` will now be the designated entry point.

**Verification:**
*   Run `python main.py` in a fresh environment to test the dependency warnings.
*   Run it in the correct environment and ensure the directories are created and the TUI launches successfully.