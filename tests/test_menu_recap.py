import unittest
from unittest.mock import MagicMock, patch
import os
import sys

# Mock dependencies
sys.modules['textual'] = MagicMock()
sys.modules['textual.app'] = MagicMock()
sys.modules['textual.widgets'] = MagicMock()
sys.modules['textual_image'] = MagicMock()
sys.modules['textual_image.widget'] = MagicMock()
sys.modules['textual.containers'] = MagicMock()
sys.modules['textual.reactive'] = MagicMock()
sys.modules['textual.message'] = MagicMock()

from unittest.mock import MagicMock, patch
import os
import sys

# Define a dummy base class for TaiMenu if textual is not present
class MockApp:
    def __init__(self, *args, **kwargs):
        pass
    def call_from_thread(self, func, *args, **kwargs):
        pass
    def query_one(self, *args, **kwargs):
        return MagicMock()
    def mount(self, *args, **kwargs):
        pass
    def scroll_end(self, *args, **kwargs):
        pass

# Mock textual dependencies more surgically
mock_textual = MagicMock()
mock_textual.app.App = MockApp
sys.modules['textual'] = mock_textual
sys.modules['textual.app'] = mock_textual.app
sys.modules['textual.widgets'] = MagicMock()
sys.modules['textual_image'] = MagicMock()
sys.modules['textual_image.widget'] = MagicMock()
sys.modules['textual.containers'] = MagicMock()
sys.modules['textual.reactive'] = MagicMock()
sys.modules['textual.message'] = MagicMock()

import menu
from menu import TaiMenu

class TestMenuRecap(unittest.TestCase):
    @patch('menu.memory_manager')
    @patch('menu.get_setting')
    def test_run_recap_long_history_logic(self, mock_get_setting, mock_memory_manager):        
        # Mock long history (20 messages)
        history = [{"role": "user", "content": f"msg {i}"} for i in range(20)]
        mock_memory_manager.load_history.return_value = history

        # Create a real instance but mock the methods we don't want to run
        app = TaiMenu(char_path=None, user_path=None)
        app.history_profile_name = "test"
        app.summarize_and_display = MagicMock()

        # Call run_recap
        app.run_recap()

        # Check if summarize_and_display was called
        app.summarize_and_display.assert_called_once()
        older, recent = app.summarize_and_display.call_args[0]
        self.assertEqual(len(older), 15)
        self.assertEqual(len(recent), 5)

    @patch('menu.memory_manager')
    @patch('menu.get_setting')
    def test_run_recap_short_history_logic(self, mock_get_setting, mock_memory_manager):       
        # Mock short history
        history = [{"role": "user", "content": "Hi"}]
        mock_memory_manager.load_history.return_value = history

        app = TaiMenu(char_path=None, user_path=None)
        app.history_profile_name = "test"
        app.add_message = MagicMock()
        app.format_rp = MagicMock(side_effect=lambda x, role: x)

        app.run_recap()

        # Should call add_message 3 times (recap header, message, recap footer)
        self.assertEqual(app.add_message.call_count, 3)
        # Should NOT call summarize_and_display
        # (Need to mock it on the instance to check it wasn't called)
        app.summarize_and_display = MagicMock()
        app.run_recap() # Run again or just check count
        app.summarize_and_display.assert_not_called()
if __name__ == '__main__':
    unittest.main()
