import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestProfileSelectScreen(unittest.TestCase):
    @patch('os.path.exists')
    @patch('os.scandir')
    def test_load_character_profiles(self, mock_scandir, mock_exists):
        """
        Test that character profiles are loaded into OptionList.
        """
        from ui.ProfileSelectScreen import ProfileSelect
        
        mock_exists.return_value = True
        
        # Create mock DirEntry objects
        entry1 = MagicMock()
        entry1.is_file.return_value = True
        entry1.is_dir.return_value = False
        entry1.name = "Eira.json"
        
        entry2 = MagicMock()
        entry2.is_file.return_value = True
        entry2.is_dir.return_value = False
        entry2.name = "Astgenne.json"
        
        mock_scandir.return_value = [entry1, entry2]
        
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
        from ui.ProfileSelectScreen import ProfileSelect
        
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

    @patch('os.path.exists')
    @patch('builtins.open')
    @patch('json.load')
    def test_update_preview(self, mock_json_load, mock_open, mock_exists):
        """
        Test that the preview card details update correctly based on loaded JSON data.
        """
        from ui.ProfileSelectScreen import ProfileSelect
        
        mock_exists.return_value = True
        mock_json_load.return_value = {
            "name": "Astgenne",
            "personality_type": "INTJ - The Decisive Nerd",
            "backstory": "Test backstory text.",
            "character_info": {
                "gender": "Female",
                "age": "20s",
                "likes": ["Coffee", "Machinery"],
                "dislikes": ["Pointless chicanery"],
                "appearance": "Slim, Liberi"
            },
            "avatar_path": "img/Astgenne.png"
        }
        
        screen = ProfileSelect()
        
        # Create mocks for all query elements
        mock_widgets = {
            "#preview_name": MagicMock(),
            "#preview_stats": MagicMock(),
            "#preview_personality": MagicMock(),
            "#preview_likes_dislikes": MagicMock(),
            "#preview_appearance": MagicMock(),
            "#preview_backstory": MagicMock(),
            "#preview_avatar_wrap": MagicMock()
        }
        
        def mock_query_one(selector, type=None):
            return mock_widgets.get(selector, MagicMock())

        with patch.object(screen, 'query_one', side_effect=mock_query_one):
            # Patch _load_and_optimize_avatar to prevent async worker threads during unittest
            with patch.object(screen, '_load_and_optimize_avatar') as mock_optimize:
                screen.update_preview("Astgenne.json")
                
                # Verify mock update calls
                mock_widgets["#preview_name"].update.assert_called_with("[bold magenta]Astgenne[/bold magenta]")
                mock_widgets["#preview_stats"].update.assert_called_with("[bold]Gender:[/bold] Female   |   [bold]Age:[/bold] 20s")
                mock_widgets["#preview_personality"].update.assert_called_with("[bold]Personality:[/bold] [italic]INTJ - The Decisive Nerd[/italic]")
                mock_widgets["#preview_backstory"].update.assert_called_with("[bold]Backstory:[/bold]\nTest backstory text.")
                
                # Check avatar optimization was triggered
                mock_optimize.assert_called_once_with("Astgenne.json", "img/Astgenne.png")

    def test_clear_preview(self):
        """
        Test that clear_preview correctly resets all detail labels.
        """
        from ui.ProfileSelectScreen import ProfileSelect
        
        screen = ProfileSelect()
        mock_widgets = {
            "#preview_name": MagicMock(),
            "#preview_stats": MagicMock(),
            "#preview_personality": MagicMock(),
            "#preview_likes_dislikes": MagicMock(),
            "#preview_appearance": MagicMock(),
            "#preview_backstory": MagicMock()
        }
        
        def mock_query_one(selector, type=None):
            return mock_widgets.get(selector, MagicMock())

        with patch.object(screen, 'query_one', side_effect=mock_query_one):
            screen.clear_preview()
            
            # Verify they are updated to empty strings or display is hidden
            mock_widgets["#preview_name"].update.assert_called_with("")
            mock_widgets["#preview_stats"].update.assert_called_with("")
            mock_widgets["#preview_personality"].update.assert_called_with("")
            mock_widgets["#preview_likes_dislikes"].update.assert_called_with("")
            mock_widgets["#preview_backstory"].update.assert_called_with("")
            self.assertFalse(mock_widgets["#preview_appearance"].display)

if __name__ == '__main__':
    unittest.main()
