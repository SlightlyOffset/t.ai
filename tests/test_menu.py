import unittest
import sys
import os
from unittest.mock import MagicMock, patch

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from ui.menu import TaiMenu, format_rp

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

    @patch('ui.menu.pick_profile')
    @patch('ui.menu.pick_user_profile')
    def test_app_init(self, mock_pick_user, mock_pick_char):
        """Ensure TaiMenu can be initialized with paths."""
        app = TaiMenu(char_path="profiles/test.json", user_path="user_profiles/test.json")
        self.assertEqual(app.char_path, "profiles/test.json")
        self.assertEqual(app.user_path, "user_profiles/test.json")

    @patch('ui.menu.TaiMenu.query')
    def test_get_last_user_message_from_ui(self, mock_query):
        """Test retrieving the last user message from UI bubbles."""
        mock_bubble = MagicMock()
        mock_bubble.raw_text = "Hello companion"
        mock_query.return_value.last.return_value = mock_bubble
        
        app = MagicMock(spec=TaiMenu)
        app.query = mock_query
        
        result = TaiMenu.get_last_user_message_from_ui(app)
        self.assertEqual(result, "Hello companion")
        mock_query.assert_called_once_with(".user_bubble")

    @patch('ui.menu.TaiMenu.get_last_user_message_from_ui')
    def test_resolve_regeneration_text_fallback(self, mock_get_last):
        """Test resolution of regeneration text falling back to UI when engine text differs or is missing."""
        app = MagicMock(spec=TaiMenu)
        app._resolve_regeneration_text = lambda et: TaiMenu._resolve_regeneration_text(app, et)
        app.get_last_user_message_from_ui = mock_get_last
        
        # Case 1: Engine text matches UI text
        mock_get_last.return_value = "Hello"
        self.assertEqual(app._resolve_regeneration_text("Hello"), "Hello")
        
        # Case 2: Engine text differs from UI text (mismatch / desync)
        mock_get_last.return_value = "Hello"
        self.assertEqual(app._resolve_regeneration_text("Previous"), "Hello")
        
        # Case 3: Engine text is None
        mock_get_last.return_value = "Hello"
        self.assertEqual(app._resolve_regeneration_text(None), "Hello")
        
        # Case 4: No UI text, fallback to engine text
        mock_get_last.return_value = None
        self.assertEqual(app._resolve_regeneration_text("Previous"), "Previous")

    @patch('ui.menu.update_setting')
    def test_on_select_changed_interaction_mode(self, mock_update_setting):
        """Test on_select_changed updates interaction_mode when interaction_mode_select changes."""
        app = MagicMock(spec=TaiMenu)
        app.on_select_changed = lambda event: TaiMenu.on_select_changed(app, event)
        app.add_message = MagicMock()

        # Select RP Mode
        event_rp = MagicMock()
        event_rp.select.id = "interaction_mode_select"
        event_rp.value = "rp"
        app.on_select_changed(event_rp)
        mock_update_setting.assert_any_call("interaction_mode", "rp")
        app.add_message.assert_any_call("Interaction mode set to [bold]RP[/bold]", role="system")

        # Select Casual Mode
        event_casual = MagicMock()
        event_casual.select.id = "interaction_mode_select"
        event_casual.value = "casual"
        app.on_select_changed(event_casual)
        mock_update_setting.assert_any_call("interaction_mode", "casual")
        app.add_message.assert_any_call("Interaction mode set to [bold]CASUAL[/bold]", role="system")

if __name__ == "__main__":
    unittest.main()
