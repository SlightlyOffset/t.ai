import json
import os
from pathlib import Path

from engines.config import get_setting
from engines.prompts import get_relationship_rule
from engines.utilities import get_character_name_from_path


DEFAULT_AVATAR_PATH = "img/No_Image_Error.png"


def resolve_selected_paths(char_path: str | None, user_path: str | None) -> tuple[str | None, str | None]:
    """Resolve profile paths from explicit args or persisted settings."""
    resolved_char_path = char_path
    resolved_user_path = user_path

    if not resolved_char_path:
        char_profile_name = get_setting("current_character_profile")
        if char_profile_name:
            potential_path = os.path.join("profiles", char_profile_name)
            if os.path.exists(potential_path):
                resolved_char_path = potential_path

    if not resolved_user_path:
        user_profile_name = get_setting("current_user_profile")
        if user_profile_name:
            potential_path = os.path.join("user_profiles", user_profile_name)
            if os.path.exists(potential_path):
                resolved_user_path = potential_path

    return resolved_char_path, resolved_user_path


def _load_json_file(path: str | None) -> dict | None:
    if not path:
        return None
    try:
        with open(path, "r", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def resolve_profile_assets(profile: dict, char_path: str) -> None:
    """Resolves character relative assets and paths to absolute or correct relative paths."""
    if not profile or not char_path:
        return
    profile_dir = os.path.dirname(char_path)

    # 1. Resolve avatar_path
    avatar = profile.get("avatar_path")
    if avatar:
        if not os.path.isabs(avatar):
            if not os.path.exists(avatar):
                rel_path = os.path.join(profile_dir, avatar)
                if os.path.exists(rel_path):
                    profile["avatar_path"] = rel_path.replace("\\", "/")
    else:
        # Default fallback if avatar.png exists in character directory
        for ext in (".png", ".jpg", ".jpeg", ".webp"):
            fallback = os.path.join(profile_dir, f"avatar{ext}")
            if os.path.exists(fallback):
                profile["avatar_path"] = fallback.replace("\\", "/")
                break

    # 2. Resolve lorebook_path
    lorebook = profile.get("lorebook_path")
    if lorebook:
        if not os.path.isabs(lorebook):
            if not os.path.exists(lorebook):
                rel_path = os.path.join(profile_dir, lorebook)
                if os.path.exists(rel_path):
                    profile["lorebook_path"] = rel_path.replace("\\", "/")
    else:
        # Default fallback if lorebook.json exists in character directory
        fallback = os.path.join(profile_dir, "lorebook.json")
        if os.path.exists(fallback):
            profile["lorebook_path"] = fallback.replace("\\", "/")

    # 3. Resolve custom_rules_path
    custom_rules = os.path.join(profile_dir, "custom_rules.md")
    if os.path.exists(custom_rules):
        profile["custom_rules_path"] = custom_rules.replace("\\", "/")


def load_profile_session(char_path: str, user_path: str | None) -> dict:
    """Load character and optional user profile data for a UI session."""
    character_profile = _load_json_file(char_path) or {}
    resolve_profile_assets(character_profile, char_path)
    user_profile = _load_json_file(user_path) if user_path else None

    colors = character_profile.get("colors", {})
    user_colors = user_profile.get("colors", {}) if user_profile else {}

    return {
        "character_profile": character_profile,
        "user_profile": user_profile,
        "ch_name": character_profile.get("name", "Assistant"),
        "user_name": (user_profile or {}).get("name", "User"),
        "char_name_lbl_color": colors.get("name_lbl", "magenta"),
        "user_name_lbl_color": user_colors.get("name_lbl", "cyan"),
        "history_profile_name": get_character_name_from_path(char_path),
    }


def resolve_avatar_abs_path(path: str | None) -> str:
    avatar_path = path or DEFAULT_AVATAR_PATH
    if not os.path.exists(avatar_path):
        avatar_path = DEFAULT_AVATAR_PATH
    return str(Path(avatar_path).absolute())


def get_initial_avatar_paths(char_path: str | None, user_path: str | None) -> tuple[str, str]:
    """Get absolute avatar image paths for compose-time sidebar image defaults."""
    init_avatar = DEFAULT_AVATAR_PATH
    init_user_avatar = DEFAULT_AVATAR_PATH

    char_data = _load_json_file(char_path)
    if char_data:
        init_avatar = char_data.get("avatar_path") or DEFAULT_AVATAR_PATH

    user_data = _load_json_file(user_path)
    if user_data:
        init_user_avatar = user_data.get("avatar_path") or DEFAULT_AVATAR_PATH

    return resolve_avatar_abs_path(init_avatar), resolve_avatar_abs_path(init_user_avatar)


def build_sidebar_state(
    character_profile: dict,
    user_profile: dict | None,
    ch_name: str,
    user_name: str,
    char_name_lbl_color: str,
    user_name_lbl_color: str,
) -> dict:
    """Build a UI-agnostic sidebar state payload."""
    char_avatar_abs = resolve_avatar_abs_path(character_profile.get("avatar_path", DEFAULT_AVATAR_PATH))
    user_avatar_abs = resolve_avatar_abs_path((user_profile or {}).get("avatar_path", DEFAULT_AVATAR_PATH))

    try:
        rel = float(character_profile.get("relationship_score", 0))
    except (ValueError, TypeError):
        rel = 0.0
    rel_rule = get_relationship_rule(rel)
 
    return {
        "char_avatar_abs": char_avatar_abs,
        "user_avatar_abs": user_avatar_abs,
        "char_label": f"Name: [bold {char_name_lbl_color}]{ch_name}[/bold {char_name_lbl_color}]",
        "status_label": f"Status: [bold {rel_rule.get('color', '#6e88ff')}]{rel_rule.get('label', 'Neutral / Acquaintance')}[/bold {rel_rule.get('color', '#6e88ff')}]",
        "rel_label": f"Score: [bold]{rel:.2f}[/bold]",
        "user_label": f"User: [bold {user_name_lbl_color}]{user_name}[/bold {user_name_lbl_color}]",
        "rel_progress": rel + 100,
    }
