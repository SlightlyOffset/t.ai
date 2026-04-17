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

    @patch("engines.profile_state.get_mood_rule", return_value={"label": "Friendly", "color": "#00ff00"})
    @patch("engines.profile_state.resolve_avatar_abs_path", side_effect=["C:\\char.png", "C:\\user.png"])
    def test_build_sidebar_state(self, _mock_avatar, _mock_mood):
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
        self.assertIn("Friendly", state["mood_label"])
        self.assertEqual(state["rel_progress"], 112)


if __name__ == "__main__":
    unittest.main()
