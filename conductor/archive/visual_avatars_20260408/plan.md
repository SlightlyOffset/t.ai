# Implementation Plan - Visual Avatar Integration

## Phase 1: Environment & Profile Setup [checkpoint: 4280bd7]
- [x] Verify `chafa` availability in the system path. 9b7fabf
- [x] Add `avatar_path` to at least one character profile (e.g., Astgenne). 9b7fabf
- [x] Implement a `render_avatar` utility that calls Chafa (Sixel) and returns an ANSI string. a043a74

## Phase 2: UI Integration
- [x] Update `TaiMenu.compose` to include an `#avatar_portrait` widget in the sidebar. ebb459d
- [x] Update `load_initial_state` to trigger avatar rendering on startup. 9981ee9
- [x] Update CSS to ensure the portrait has proper padding and alignment. 4c9d945

## Phase 3: Refactor to Real Images (textual-image)
- [x] Document the new dependency `textual-image` in `tech-stack.md`. a99ebbc
- [x] Install the `textual-image` package. a99ebbc
- [x] Update `menu.py` to use `textual_image.widget.Image` instead of the `render_avatar` utility. a99ebbc
- [x] Remove `is_chafa_available` and `render_avatar` from `engines/utilities.py` and delete related tests. a99ebbc

## Phase 4: Validation
- [x] Test with different image formats (PNG, JPG). 7201dba
- [x] Verify behavior on terminals lacking Sixel/Kitty protocol support. 7201dba
