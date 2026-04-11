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

from menu import TaiMenu

class TestMenuRecap(unittest.TestCase):
    @patch('menu.memory_manager')
    def test_run_recap_long_history_logic(self, mock_memory_manager):
        # Mock long history (20 messages)
        history = [{"role": "user", "content": f"msg {i}"} for i in range(20)]
        mock_memory_manager.load_history.return_value = history
        
        # Create a dummy object
        app = MagicMock()
        app.history_profile_name = "test"
        
        # Manually call run_recap
        TaiMenu.run_recap(app)
        
        # Check if summarize_and_display was called on the dummy app
        app.summarize_and_display.assert_called_once()
        older, recent = app.summarize_and_display.call_args[0]
        self.assertEqual(len(older), 15)
        self.assertEqual(len(recent), 5)

    @patch('menu.memory_manager')
    def test_run_recap_short_history_logic(self, mock_memory_manager):
        # Mock short history
        history = [{"role": "user", "content": "Hi"}]
        mock_memory_manager.load_history.return_value = history
        
        app = MagicMock()
        app.history_profile_name = "test"
        app.format_rp.side_effect = lambda x, role: x
        
        TaiMenu.run_recap(app)
        
        # Should call add_message 3 times (recap header, message, recap footer)
        self.assertEqual(app.add_message.call_count, 3)
        app.summarize_and_display.assert_not_called()

if __name__ == '__main__':
    unittest.main()
