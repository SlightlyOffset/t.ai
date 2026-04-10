# Specification - Visual Avatar Integration (Phase 5)

## Overview
Implement character portraits within the **t.ai** TUI sidebar using **Chafa** for terminal-based image rendering. This fulfills the "Phase 5: Visual Representation" goal while remaining lightweight and CLI-first.

## Functional Requirements
- **Portrait Display**: Show a terminal-rendered version of the companion's image at the top of the sidebar.
- **High Fidelity**: Utilize Chafa's Unicode/ANSI capabilities to provide colored, high-quality pixel-style art.
- **Dynamic Loading**: Automatically update the portrait when the character profile is changed.
- **Robust Fallback**: If Chafa is not installed or the image is missing, display a stylized ASCII placeholder box.

## Technical Requirements
- **Chafa Integration**: Invoke `chafa` as a subprocess and capture the stdout (ANSI string).
- **Responsive Scaling**: Calculate appropriate `--size` based on the sidebar width (fixed at 35 chars).
- **Profile Extension**: Update character `.json` files to include an `avatar_path` field.

## Acceptance Criteria
- [ ] Portraits appear at the top of the sidebar upon launch.
- [ ] Portraits respect the sidebar width without breaking the layout.
- [ ] The app handles missing `chafa.exe` gracefully without crashing.
- [ ] The UI remains responsive during the initial "rendering" of the image.
