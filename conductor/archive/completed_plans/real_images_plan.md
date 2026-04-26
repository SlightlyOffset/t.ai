# Plan: Switch to Real Images using textual-image

## Objective
The user requested to display real images instead of ANSI symbols for the character portrait in the TUI sidebar. The current implementation uses `chafa` to generate ANSI blocks. To display actual images (using Sixel or Kitty's Terminal Graphics Protocol), we will integrate the `textual-image` Python library.

## Key Files & Context
- `menu.py`: Houses the Textual UI.
- `engines/utilities.py`: Currently holds the `chafa`-based rendering logic.
- `tech-stack.md`: Documents the project's tech stack.
- `conductor/tracks/visual_avatars_20260408/plan.md`: The active tracking plan.

## Implementation Steps
1. **Update Tech Stack:** Document the new `textual-image` dependency in `tech-stack.md`.
2. **Install Dependency:** Run `pip install textual-image`.
3. **Update UI Logic (`menu.py`):**
   - Import `Image` from `textual_image.widget`.
   - Replace the `Static("", id="avatar_portrait")` placeholder with the native `Image(avatar_path, id="avatar_portrait")` widget.
4. **Cleanup (`engines/utilities.py`):**
   - Remove the `is_chafa_available` and `render_avatar` utility functions.
   - Delete associated tests in `tests/test_visual_avatar.py`.
5. **Update Track Plan:**
   - Update `conductor/tracks/visual_avatars_20260408/plan.md` to reflect the new direction for Phase 3 and Phase 4.

## Verification & Testing
- Start `menu.py` and load the Astgenne profile.
- Ensure the image renders correctly if the terminal supports Sixel/Kitty.
- Verify that Textual correctly falls back to Unicode blocks if the terminal lacks protocol support.