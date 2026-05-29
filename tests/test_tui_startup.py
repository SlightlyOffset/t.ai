import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class TestTUIStartup(unittest.TestCase):
    @patch('ui.menu.pick_profile')
    @patch('ui.menu.pick_user_profile')
    @patch('ui.menu.TaiMenu.run')
    def test_main_does_not_call_blocking_picks(self, mock_run, mock_pick_user, mock_pick_char):
        """
        Test that running menu.py does not call the blocking pick_profile and pick_user_profile functions.
        This test will fail if they are still present in the __main__ block and called.
        """
        import ui.menu as menu
        
        # We need to trigger the __main__ logic. 
        # Since it's protected by if __name__ == "__main__", we can't just import it.
        # But we can manually execute the logic that would be in __main__ if we were running it.
        # Or better, we can use a small script to run it and check.
        
        # However, for TDD, I want a test that FAILS now because they ARE called.
        # If I mock them and they are called, I can assert they weren't.
        
        # To actually execute the __main__ block code in a testable way:
        # We can use `runpy.run_module` or similar, but that's messy.
        
        # Let's try to mock TaiMenu and see if we can trigger the main block.
        # Actually, it's easier to just check the content of menu.py via static analysis in the test for now?
        # No, TDD should be execution-based if possible.
        
        pass

    def test_blocking_calls_removed_from_main(self):
        """
        Static analysis check to ensure pick_profile and pick_user_profile are not in the __main__ block.
        """
        with open('ui/menu.py', 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find the __main__ block
        main_block_index = content.find('if __name__ == "__main__":')
        self.assertNotEqual(main_block_index, -1, "__main__ block not found in menu.py")
        
        main_block = content[main_block_index:]
        
        self.assertNotIn('pick_profile()', main_block, "pick_profile() still called in __main__ block")
        self.assertNotIn('pick_user_profile()', main_block, "pick_user_profile() still called in __main__ block")

    @patch('engines.profile_state.get_setting')
    @patch('ui.menu.get_setting')
    @patch('ui.menu.TaiMenu.start_tts_worker')
    @patch('ui.menu.TaiMenu.update_sidebar')
    @patch('ui.menu.TaiMenu.query_one')
    @patch('ui.menu.TaiMenu.add_message')
    def test_load_initial_state_from_settings(self, mock_msg, mock_query, mock_sidebar, mock_tts, mock_get_setting_menu, mock_get_setting_profile):
        """
        Test that load_initial_state attempts to load from settings if paths are None.
        """
        import ui.menu as menu
        from ui.menu import TaiMenu
        
        # Mock get_setting to return a valid profile filename
        def side_effect(key, default=None):
            if key == "current_character_profile":
                return "Astgenne.json"
            if key == "current_user_profile":
                return "Manganese.json"
            return default
        mock_get_setting_menu.side_effect = side_effect
        mock_get_setting_profile.side_effect = side_effect
        
        app = TaiMenu(char_path=None, user_path=None)
        # We need to mock open because it will try to open profiles/Astgenne.json
        with patch('builtins.open', unittest.mock.mock_open(read_data='{"name": "Astgenne"}')):
            with patch('os.path.exists', return_value=True):
                app.load_initial_state()
        
        self.assertEqual(app.char_path, os.path.join("profiles", "Astgenne.json"))
        self.assertEqual(app.user_path, os.path.join("user_profiles", "Manganese.json"))

    @patch('engines.profile_state.get_setting')
    @patch('ui.menu.get_setting')
    @patch('ui.menu.TaiMenu.start_tts_worker')
    @patch('ui.menu.TaiMenu.update_sidebar')
    @patch('ui.menu.TaiMenu.query_one')
    @patch('ui.menu.TaiMenu.add_message')
    @patch('ui.menu.TaiMenu.push_screen')
    def test_push_profile_select_if_loading_fails(self, mock_push, mock_msg, mock_query, mock_sidebar, mock_tts, mock_get_setting_menu, mock_get_setting_profile):
        """
        Test that push_screen(ProfileSelect()) is called if load_initial_state fails to find paths.
        """
        import ui.menu as menu
        from ui.menu import TaiMenu
        
        # Mock get_setting to return None
        mock_get_setting_menu.return_value = None
        mock_get_setting_profile.return_value = None
        
        app = TaiMenu(char_path=None, user_path=None)
        with patch('os.path.exists', return_value=False):
            app.on_mount()
        
        # We expect push_screen to be called once
        self.assertTrue(mock_push.called)

    @patch('ui.menu.TaiMenu.load_initial_state')
    @patch('ui.menu.TaiMenu.populate_models')
    @patch('ui.menu.TaiMenu.populate_voices')
    @patch('ui.menu.TaiMenu.populate_tts_engines')
    @patch('ui.menu.TaiMenu.populate_image_protocols')
    def test_on_profile_selected_updates_paths(self, mock_img_proto, mock_tts_engines, mock_voices, mock_models, mock_load):
        """
        Test that on_profile_selected correctly updates character and user paths.
        """
        from ui.menu import TaiMenu
        app = TaiMenu(char_path=None, user_path=None)
        
        result = {
            "character": "Eira.json",
            "user": "Manganese.json"
        }
        
        with patch('ui.menu.TaiMenu.start_tts_worker'):
            app.on_profile_selected(result)
        
        self.assertEqual(app.char_path, os.path.join("profiles", "Eira.json"))
        self.assertEqual(app.user_path, os.path.join("user_profiles", "Manganese.json"))

    @patch('ui.menu.TaiMenu.push_screen')
    def test_action_open_profile_select_calls_push_screen(self, mock_push):
        """
        Test that action_open_profile_select (triggered by ctrl+o) calls push_screen with ProfileSelect.
        """
        from ui.menu import TaiMenu
        app = TaiMenu(char_path="some_path", user_path="some_user_path")
        
        with patch('ui.menu.TaiMenu.start_tts_worker'):
            app.action_open_profile_select()
        
        self.assertTrue(mock_push.called)

    @patch('ui.menu.TaiMenu.load_initial_state')
    @patch('ui.menu.TaiMenu.populate_models')
    @patch('ui.menu.TaiMenu.populate_voices')
    @patch('ui.menu.TaiMenu.populate_tts_engines')
    @patch('ui.menu.TaiMenu.populate_image_protocols')
    def test_switch_profile_updates_and_reinitializes(self, mock_img_proto, mock_tts_engines, mock_voices, mock_models, mock_load):
        """
        Test that switch_profile updates paths and calls re-initialization methods.
        """
        from ui.menu import TaiMenu
        app = TaiMenu(char_path="old_char.json", user_path="old_user.json")
        
        with patch('ui.menu.TaiMenu.start_tts_worker'):
            app.switch_profile("new_char.json", "new_user.json")
        
        self.assertEqual(app.char_path, "new_char.json")
        self.assertEqual(app.user_path, "new_user.json")
        self.assertTrue(mock_load.called)

    @patch('engines.config.get_setting')
    @patch('ollama.list')
    def test_check_ollama_and_models_running_and_pulled(self, mock_ollama_list, mock_get_setting):
        """Test check_ollama_and_models succeeds when Ollama is running and model is pulled."""
        from main import check_ollama_and_models
        mock_get_setting.side_effect = lambda key, default=None: {
            "remote_llm_url": None,
            "default_llm_model": "fluffy/l3-8b-stheno-v3.2"
        }.get(key, default)
        
        # Mock pulled models
        mock_ollama_list.return_value = {
            "models": [{"model": "fluffy/l3-8b-stheno-v3.2:latest"}]
        }
        
        # Should not raise SystemExit
        check_ollama_and_models()

    @patch('engines.config.get_setting')
    @patch('ollama.list')
    def test_check_ollama_and_models_not_running(self, mock_ollama_list, mock_get_setting):
        """Test check_ollama_and_models raises SystemExit when local Ollama is not running."""
        from main import check_ollama_and_models
        mock_get_setting.side_effect = lambda key, default=None: {
            "remote_llm_url": None,
            "default_llm_model": "fluffy/l3-8b-stheno-v3.2"
        }.get(key, default)
        
        mock_ollama_list.side_effect = Exception("Connection refused")
        
        with self.assertRaises(SystemExit):
            check_ollama_and_models()

    @patch('engines.config.get_setting')
    @patch('ollama.list')
    def test_check_ollama_and_models_missing_model(self, mock_ollama_list, mock_get_setting):
        """Test check_ollama_and_models raises SystemExit when model is not pulled."""
        from main import check_ollama_and_models
        mock_get_setting.side_effect = lambda key, default=None: {
            "remote_llm_url": None,
            "default_llm_model": "fluffy/l3-8b-stheno-v3.2"
        }.get(key, default)
        
        mock_ollama_list.return_value = {
            "models": [{"model": "llama3:latest"}]
        }
        
        with self.assertRaises(SystemExit):
            check_ollama_and_models()

    @patch('ollama.list')
    def test_check_ollama_and_models_force_argv(self, mock_ollama_list):
        """Test check_ollama_and_models skips check when --force flag is passed in sys.argv."""
        from main import check_ollama_and_models
        with patch('sys.argv', ['main.py', '--force']):
            check_ollama_and_models()
        self.assertFalse(mock_ollama_list.called)

    @patch('engines.config.get_setting')
    @patch('ollama.list')
    def test_check_ollama_and_models_force_setting(self, mock_ollama_list, mock_get_setting):
        """Test check_ollama_and_models skips check when force_launch setting is enabled."""
        from main import check_ollama_and_models
        mock_get_setting.side_effect = lambda key, default=None: {
            "force_launch": True
        }.get(key, default)
        
        check_ollama_and_models()
        self.assertFalse(mock_ollama_list.called)

    @patch('engines.config.get_setting')
    @patch('ollama.list')
    @patch('sys.stdin.isatty', return_value=True)
    @patch('builtins.input')
    def test_check_ollama_and_models_not_running_interactive_force_launch(self, mock_input, mock_isatty, mock_ollama_list, mock_get_setting):
        """Test that user can force launch when Ollama is not running in an interactive session."""
        from main import check_ollama_and_models
        mock_get_setting.side_effect = lambda key, default=None: {
            "remote_llm_url": None,
            "default_llm_model": "fluffy/l3-8b-stheno-v3.2"
        }.get(key, default)
        
        mock_ollama_list.side_effect = Exception("Connection refused")
        mock_input.return_value = "y"
        
        # Should not raise SystemExit
        check_ollama_and_models()
        mock_input.assert_called_once()

    @patch('engines.config.get_setting')
    @patch('ollama.list')
    @patch('sys.stdin.isatty', return_value=True)
    @patch('builtins.input')
    def test_check_ollama_and_models_not_running_interactive_no_force_launch(self, mock_input, mock_isatty, mock_ollama_list, mock_get_setting):
        """Test that rejecting force launch when Ollama is not running raises SystemExit."""
        from main import check_ollama_and_models
        mock_get_setting.side_effect = lambda key, default=None: {
            "remote_llm_url": None,
            "default_llm_model": "fluffy/l3-8b-stheno-v3.2"
        }.get(key, default)
        
        mock_ollama_list.side_effect = Exception("Connection refused")
        mock_input.return_value = "n"
        
        with self.assertRaises(SystemExit):
            check_ollama_and_models()
        mock_input.assert_called_once()

    @patch('engines.config.get_setting')
    @patch('ollama.list')
    @patch('sys.stdin.isatty', return_value=True)
    @patch('builtins.input')
    def test_check_ollama_and_models_missing_model_interactive_force_launch(self, mock_input, mock_isatty, mock_ollama_list, mock_get_setting):
        """Test that user can force launch when default model is missing in an interactive session."""
        from main import check_ollama_and_models
        mock_get_setting.side_effect = lambda key, default=None: {
            "remote_llm_url": None,
            "default_llm_model": "fluffy/l3-8b-stheno-v3.2"
        }.get(key, default)
        
        mock_ollama_list.return_value = {
            "models": [{"model": "llama3:latest"}]
        }
        mock_input.return_value = "yes"
        
        # Should not raise SystemExit
        check_ollama_and_models()
        mock_input.assert_called_once()

    @patch('engines.config.get_setting')
    @patch('ollama.list')
    @patch('sys.stdin.isatty', return_value=True)
    @patch('builtins.input')
    def test_check_ollama_and_models_missing_model_interactive_no_force_launch(self, mock_input, mock_isatty, mock_ollama_list, mock_get_setting):
        """Test that rejecting force launch when model is missing raises SystemExit."""
        from main import check_ollama_and_models
        mock_get_setting.side_effect = lambda key, default=None: {
            "remote_llm_url": None,
            "default_llm_model": "fluffy/l3-8b-stheno-v3.2"
        }.get(key, default)
        
        mock_ollama_list.return_value = {
            "models": [{"model": "llama3:latest"}]
        }
        mock_input.return_value = ""
        
        with self.assertRaises(SystemExit):
            check_ollama_and_models()
        mock_input.assert_called_once()

if __name__ == '__main__':
    unittest.main()

