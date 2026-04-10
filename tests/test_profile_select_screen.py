import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestProfileSelectScreen(unittest.TestCase):
    @patch('os.path.exists')
    @patch('os.listdir')
    def test_load_character_profiles(self, mock_listdir, mock_exists):
        """
        Test that character profiles are loaded into OptionList.
        """
        from ProfileSelectScreen import ProfileSelect
        
        mock_exists.return_value = True
        mock_listdir.return_value = ["Eira.json", "Astgenne.json"]
        
        screen = ProfileSelect()
        mock_option_list = MagicMock()
        mock_label = MagicMock()
        
        def mock_query_one(selector, type=None):
            if selector == "#profile_list": return mock_option_list
            if selector == "#selection_label": return mock_label
            return MagicMock()

        with patch.object(screen, 'query_one', side_effect=mock_query_one):
            screen.load_character_profiles()
        
        # Should have cleared and added two options
        self.assertEqual(mock_option_list.clear_options.call_count, 1)
        self.assertEqual(mock_option_list.add_option.call_count, 2)

    @patch('os.path.exists')
    @patch('os.listdir')
    def test_load_user_profiles(self, mock_listdir, mock_exists):
        """
        Test that user profiles are loaded into OptionList.
        """
        from ProfileSelectScreen import ProfileSelect
        
        mock_exists.return_value = True
        mock_listdir.return_value = ["Manganese.json"]
        
        screen = ProfileSelect()
        mock_option_list = MagicMock()
        mock_label = MagicMock()
        
        def mock_query_one(selector, type=None):
            if selector == "#profile_list": return mock_option_list
            if selector == "#selection_label": return mock_label
            return MagicMock()

        with patch.object(screen, 'query_one', side_effect=mock_query_one):
            screen.load_user_profiles()
        
        self.assertEqual(mock_option_list.add_option.call_count, 1)
        self.assertFalse(screen.choosing_character)

if __name__ == '__main__':
    unittest.main()
