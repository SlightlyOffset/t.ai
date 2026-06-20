import unittest
import os
from unittest.mock import patch

from engines.profile_state import build_sidebar_state, resolve_selected_paths


class TestProfileState(unittest.TestCase):
    @patch("engines.profile_state.os.path.exists", return_value=True)
    @patch("engines.profile_state.get_setting")
    def test_resolve_selected_paths_from_settings(self, mock_get_setting, _mock_exists):
        mock_get_setting.side_effect = lambda key: {
            "current_character_profile": "Char.json",
            "current_user_profile": "User.json",
        }.get(key)
        char_path, user_path = resolve_selected_paths(None, None)
        self.assertEqual(char_path, os.path.join("profiles", "Char.json"))
        self.assertEqual(user_path, os.path.join("user_profiles", "User.json"))

    @patch("engines.profile_state.get_relationship_rule", return_value={"label": "Friendly", "color": "#00ff00"})
    @patch("engines.profile_state.resolve_avatar_abs_path", side_effect=["C:\\char.png", "C:\\user.png"])
    def test_build_sidebar_state(self, _mock_avatar, _mock_rel):
        state = build_sidebar_state(
            character_profile={"relationship_score": 12, "avatar_path": "char.png"},
            user_profile={"avatar_path": "user.png"},
            ch_name="Nova",
            user_name="Alex",
            char_name_lbl_color="magenta",
            user_name_lbl_color="cyan",
        )
        self.assertEqual(state["char_avatar_abs"], "C:\\char.png")
        self.assertEqual(state["user_avatar_abs"], "C:\\user.png")
        self.assertIn("Nova", state["char_label"])
        self.assertIn("Friendly", state["status_label"])
        self.assertEqual(state["rel_progress"], 112)

    def test_get_character_name_from_path(self):
        from engines.utilities import get_character_name_from_path
        self.assertEqual(get_character_name_from_path("profiles/aiko/profile.json"), "aiko")
        self.assertEqual(get_character_name_from_path("profiles/aiko/profile"), "aiko")
        self.assertEqual(get_character_name_from_path("profiles/aiko.json"), "aiko")
        self.assertEqual(get_character_name_from_path("aiko"), "aiko")
        self.assertEqual(get_character_name_from_path(""), "")
        self.assertEqual(get_character_name_from_path(None), "")

    @patch("engines.profile_state.os.path.exists")
    def test_resolve_profile_assets(self, mock_exists):
        from engines.profile_state import resolve_profile_assets
        mock_exists.side_effect = lambda path: path.startswith("profiles/") or path.endswith("custom_rules.md")
        profile = {
            "avatar_path": "avatar.png",
            "lorebook_path": "lorebook.json"
        }
        resolve_profile_assets(profile, "profiles/aiko/profile.json")
        self.assertEqual(profile["avatar_path"], "profiles/aiko/avatar.png")
        self.assertEqual(profile["lorebook_path"], "profiles/aiko/lorebook.json")
        self.assertEqual(profile["custom_rules_path"], "profiles/aiko/custom_rules.md")

    @patch("engines.prompts.os.path.exists", return_value=True)
    @patch("engines.prompts.load_user_profile", return_value=None)
    def test_custom_rules_override(self, mock_load_user, mock_exists):
        from unittest.mock import mock_open
        from engines.prompts import build_system_prompt
        profile = {
            "name": "aiko",
            "custom_rules_path": "profiles/aiko/custom_rules.md"
        }
        with patch("builtins.open", mock_open(read_data="custom rules content")):
            prompt = build_system_prompt(profile, 0, mode="rp")
        self.assertIn("custom rules content", prompt)


if __name__ == "__main__":
    unittest.main()
