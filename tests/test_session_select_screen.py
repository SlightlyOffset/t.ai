import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestSessionSelectScreen(unittest.TestCase):
    @patch('os.path.exists')
    @patch('os.makedirs')
    @patch('os.listdir')
    @patch('engines.config.get_setting')
    def test_session_select_screen_init_and_refresh(self, mock_get_setting, mock_listdir, mock_makedirs, mock_exists):
        """
        Test that SessionSelectScreen instantiates and refreshes option list correctly.
        """
        from ui.SessionSelectScreen import SessionSelectScreen
        
        mock_exists.return_value = True
        mock_listdir.return_value = ["default_history.json", "adventure_history.json"]
        mock_get_setting.return_value = "default"
        
        screen = SessionSelectScreen("Meryl")
        self.assertEqual(screen.character_name, "Meryl")
        
        mock_option_list = MagicMock()
        
        def mock_query_one(selector, type=None):
            if selector == "#session_list":
                return mock_option_list
            return MagicMock()
            
        with patch.object(screen, 'query_one', side_effect=mock_query_one):
            screen.refresh_sessions()
            
        self.assertEqual(mock_option_list.clear_options.call_count, 1)
        self.assertEqual(mock_option_list.add_option.call_count, 2)

if __name__ == '__main__':
    unittest.main()
