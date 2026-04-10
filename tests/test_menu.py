import unittest
import sys
import os
from unittest.mock import MagicMock, patch

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from menu import TaiMenu, format_rp

class TestMenu(unittest.TestCase):
    def test_format_rp(self):
        """Test the helper that italicizes narration."""
        text = "Hello *waves* how are you?"
        expected = "Hello [i][dim]waves[/dim][/i] how are you?"
        self.assertEqual(format_rp(text), expected)

    def test_format_rp_no_asterisks(self):
        self.assertEqual(format_rp("Hello"), "Hello")

    def test_format_rp_unclosed_asterisk(self):
        # Current implementation splits and italicizes odd indices
        # "Hello *waves" -> ["Hello ", "waves"] -> "Hello [i][dim]waves[/dim][/i]"
        # This is acceptable behavior for a simple regex-less helper.
        text = "Hello *waves"
        expected = "Hello [i][dim]waves[/dim][/i]"
        self.assertEqual(format_rp(text), expected)

    @patch('menu.pick_profile')
    @patch('menu.pick_user_profile')
    def test_app_init(self, mock_pick_user, mock_pick_char):
        """Ensure TaiMenu can be initialized with paths."""
        app = TaiMenu(char_path="profiles/test.json", user_path="user_profiles/test.json")
        self.assertEqual(app.char_path, "profiles/test.json")
        self.assertEqual(app.user_path, "user_profiles/test.json")

if __name__ == "__main__":
    unittest.main()
