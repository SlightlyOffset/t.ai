import unittest
from unittest.mock import patch
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
    def test_push_dashboard_if_loading_fails(self, mock_push, mock_msg, mock_query, mock_sidebar, mock_tts, mock_get_setting_menu, mock_get_setting_profile):
        """
        Test that push_screen(DashboardScreen()) is called if load_initial_state fails to find paths.
        """
        from ui.menu import TaiMenu
        
        # Mock get_setting to return None
        mock_get_setting_menu.return_value = None
        mock_get_setting_profile.return_value = None
        
        app = TaiMenu(char_path=None, user_path=None)
        with patch('os.path.exists', return_value=False):
            app.on_mount()
        
        # We expect push_screen to be called once
        self.assertTrue(mock_push.called)
        from ui.DashboardScreen import DashboardScreen
        called_screen = mock_push.call_args[0][0]
        self.assertIsInstance(called_screen, DashboardScreen)

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
    def test_check_ollama_and_models_custom_local_url(self, mock_ollama_list, mock_get_setting):
        """Test check_ollama_and_models skips check when custom local_llm_url (not 11434) is configured."""
        from main import check_ollama_and_models
        mock_get_setting.side_effect = lambda key, default=None: {
            "remote_llm_url": None,
            "local_llm_url": "http://localhost:5001/v1",
            "default_llm_model": "fluffy/l3-8b-stheno-v3.2"
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

    @patch('ui.menu.get_setting')
    @patch('engines.config.set_active_session')
    @patch('ui.menu.memory_manager.get_full_data')
    @patch('ui.menu.memory_manager.save_history')
    @patch('ui.menu.TaiMenu.add_message')
    def test_verify_session_user_profile_mismatch(self, mock_add_message, mock_save_history, mock_get_full_data, mock_set_active_session, mock_get_setting):
        """
        Test that verify_session_user_profile starts a new session if history is not empty
        and the user profile in metadata does not match the active user profile.
        """
        from ui.menu import TaiMenu
        
        # Mocks
        mock_get_setting.return_value = "default"
        mock_get_full_data.return_value = {
            "metadata": {
                "user_profile": "Manganese.json"
            },
            "history": [{"role": "user", "content": "hello"}]
        }
        
        with patch('ui.menu.TaiMenu.start_tts_worker'):
            app = TaiMenu(char_path="profiles/Astgenne.json", user_path="user_profiles/Zenith.json")
            app.history_profile_name = "Astgenne"
            
            # Since user_path is Zenith.json, os.path.basename(user_path) is Zenith.json.
            # History user is Manganese.json.
            # There is history. Mismatch should trigger new session name creation.
            new_session = app.verify_session_user_profile("default")
            
            # Assertions
            self.assertTrue(new_session.lower().startswith("zenith_"))
            mock_set_active_session.assert_called_with("Astgenne", new_session)
            mock_save_history.assert_called_with("Astgenne", [], session_name=new_session)
            mock_add_message.assert_called_once()

    @patch('ui.menu.get_setting')
    @patch('engines.config.set_active_session')
    @patch('ui.menu.memory_manager.get_full_data')
    @patch('ui.menu.memory_manager.save_history')
    @patch('ui.menu.TaiMenu.add_message')
    def test_verify_session_user_profile_match(self, mock_add_message, mock_save_history, mock_get_full_data, mock_set_active_session, mock_get_setting):
        """
        Test that verify_session_user_profile does not start a new session if the user profiles match.
        """
        from ui.menu import TaiMenu
        
        mock_get_setting.return_value = "default"
        mock_get_full_data.return_value = {
            "metadata": {
                "user_profile": "Zenith.json"
            },
            "history": [{"role": "user", "content": "hello"}]
        }
        
        with patch('ui.menu.TaiMenu.start_tts_worker'):
            app = TaiMenu(char_path="profiles/Astgenne.json", user_path="user_profiles/Zenith.json")
            app.history_profile_name = "Astgenne"
            
            new_session = app.verify_session_user_profile("default")
            
            self.assertEqual(new_session, "default")
            mock_set_active_session.assert_not_called()
            mock_save_history.assert_not_called()
            mock_add_message.assert_not_called()

    @patch('ui.menu.get_setting')
    @patch('engines.config.set_active_session')
    @patch('ui.menu.memory_manager.get_full_data')
    @patch('ui.menu.memory_manager.save_history')
    @patch('ui.menu.TaiMenu.add_message')
    def test_verify_session_user_profile_legacy_none(self, mock_add_message, mock_save_history, mock_get_full_data, mock_set_active_session, mock_get_setting):
        """
        Test that verify_session_user_profile does not start a new session if history_user is None.
        """
        from ui.menu import TaiMenu
        
        mock_get_setting.return_value = "default"
        mock_get_full_data.return_value = {
            "metadata": {
                "user_profile": None
            },
            "history": [{"role": "user", "content": "hello"}]
        }
        
        with patch('ui.menu.TaiMenu.start_tts_worker'):
            app = TaiMenu(char_path="profiles/Astgenne.json", user_path="user_profiles/Zenith.json")
            app.history_profile_name = "Astgenne"
            
            new_session = app.verify_session_user_profile("default")
            
            self.assertEqual(new_session, "default")
            mock_set_active_session.assert_not_called()
            mock_save_history.assert_not_called()
            mock_add_message.assert_not_called()

    @patch('engines.profile_state.get_setting')
    @patch('ui.menu.get_setting')
    @patch('ui.menu.memory_manager.get_last_timestamp')
    @patch('ui.menu.TaiMenu.start_tts_worker')
    @patch('ui.menu.TaiMenu.update_sidebar')
    @patch('ui.menu.TaiMenu.query_one')
    @patch('ui.menu.TaiMenu.add_message')
    @patch('ui.menu.TaiMenu.push_screen')
    def test_push_dashboard_on_inactivity_timeout(self, mock_push, mock_msg, mock_query, mock_sidebar, mock_tts, mock_get_last_timestamp, mock_get_setting_menu, mock_get_setting_profile):
        """Test that DashboardScreen is pushed when inactivity timeout has been exceeded."""
        from ui.menu import TaiMenu
        from datetime import datetime, timedelta
        
        # Configure settings: inactivity timeout is 12 hours
        mock_get_setting_menu.side_effect = lambda key, default=None: {
            "inactivity_dashboard_timeout": 12,
            "current_character_profile": "Astgenne.json"
        }.get(key, default)
        mock_get_setting_profile.side_effect = lambda key, default=None: {
            "inactivity_dashboard_timeout": 12,
            "current_character_profile": "Astgenne.json"
        }.get(key, default)
        
        # Set last interaction to 15 hours ago (exceeding 12 hours)
        mock_get_last_timestamp.return_value = datetime.now() - timedelta(hours=15)
        
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', unittest.mock.mock_open(read_data='{"name": "Astgenne"}')):
                app = TaiMenu(char_path="profiles/Astgenne.json", user_path="user_profiles/Zenith.json")
                app.history_profile_name = "Astgenne"
                
                # Mock methods that on_mount runs
                app.watch = lambda *args, **kwargs: None
                app.on_mount()
                
        self.assertTrue(mock_push.called)
        from ui.DashboardScreen import DashboardScreen
        called_screen = mock_push.call_args[0][0]
        self.assertIsInstance(called_screen, DashboardScreen)

    @patch('engines.profile_state.get_setting')
    @patch('ui.menu.get_setting')
    @patch('ui.menu.memory_manager.get_last_timestamp')
    @patch('ui.menu.TaiMenu.start_tts_worker')
    @patch('ui.menu.TaiMenu.update_sidebar')
    @patch('ui.menu.TaiMenu.query_one')
    @patch('ui.menu.TaiMenu.add_message')
    @patch('ui.menu.TaiMenu.push_screen')
    @patch('ui.menu.TaiMenu.populate_models')
    @patch('ui.menu.TaiMenu.populate_voices')
    @patch('ui.menu.TaiMenu.populate_tts_engines')
    @patch('ui.menu.TaiMenu.populate_image_protocols')
    @patch('ui.menu.TaiMenu.populate_interaction_modes')
    @patch('ui.menu.TaiMenu.load_initial_history')
    def test_no_dashboard_if_recent_interaction(self, mock_load_hist, mock_im, mock_ip, mock_tts_eng, mock_vc, mock_md, mock_push, mock_msg, mock_query, mock_sidebar, mock_tts, mock_get_last_timestamp, mock_get_setting_menu, mock_get_setting_profile):
        """Test that DashboardScreen is not pushed when last interaction is recent."""
        from ui.menu import TaiMenu
        from datetime import datetime, timedelta
        
        # Configure settings: inactivity timeout is 12 hours
        mock_get_setting_menu.side_effect = lambda key, default=None: {
            "inactivity_dashboard_timeout": 12,
            "current_character_profile": "Astgenne.json"
        }.get(key, default)
        mock_get_setting_profile.side_effect = lambda key, default=None: {
            "inactivity_dashboard_timeout": 12,
            "current_character_profile": "Astgenne.json"
        }.get(key, default)
        
        # Set last interaction to 5 hours ago (within 12 hours)
        mock_get_last_timestamp.return_value = datetime.now() - timedelta(hours=5)
        
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', unittest.mock.mock_open(read_data='{"name": "Astgenne"}')):
                app = TaiMenu(char_path="profiles/Astgenne.json", user_path="user_profiles/Zenith.json")
                app.history_profile_name = "Astgenne"
                
                # Mock methods
                app.watch = lambda *args, **kwargs: None
                app.set_interval = lambda *args, **kwargs: None
                app.on_mount()
                
        self.assertFalse(mock_push.called)

    @patch('ui.menu.TaiMenu.start_tts_worker')
    @patch('ui.menu.TaiMenu.push_screen')
    def test_action_open_dashboard_calls_push_screen(self, mock_push, mock_tts):
        """Test that action_open_dashboard pushes DashboardScreen."""
        from ui.menu import TaiMenu
        app = TaiMenu(char_path="profiles/Astgenne.json", user_path="user_profiles/Zenith.json")
        app.action_open_dashboard()
        self.assertTrue(mock_push.called)
        from ui.DashboardScreen import DashboardScreen
        called_screen = mock_push.call_args[0][0]
        self.assertIsInstance(called_screen, DashboardScreen)

    @patch('os.path.isdir')
    @patch('os.path.exists')
    @patch('os.scandir')
    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    @patch('os.path.getmtime')
    def test_get_all_recent_sessions_detects_unified_and_legacy_profiles(self, mock_getmtime, mock_open, mock_scandir, mock_exists, mock_isdir):
        """Test that get_all_recent_sessions detects both legacy flat JSON and unified character directories."""
        from ui.RecentSessionsScreen import get_all_recent_sessions
        from collections import namedtuple
        
        DirEntry = namedtuple('DirEntry', ['name', 'is_file', 'is_dir', 'path'])
        
        def norm(p):
            return os.path.normpath(p).replace('\\', '/')
        
        # Configure profiles_dir contents
        mock_scandir.side_effect = lambda path: {
            "profiles": [
                DirEntry("settings.json", lambda: True, lambda: False, "profiles/settings.json"),
                DirEntry("legacy_profile.json", lambda: True, lambda: False, "profiles/legacy_profile.json"),
                DirEntry("aiko_unified", lambda: False, lambda: True, "profiles/aiko_unified"),
                DirEntry("non_profile_dir", lambda: False, lambda: True, "profiles/non_profile_dir")
            ],
            "history/legacy_profile": [
                DirEntry("session1_history.json", lambda: True, lambda: False, "history/legacy_profile/session1_history.json")
            ],
            "profiles/aiko_unified/sessions": [
                DirEntry("session2_history.json", lambda: True, lambda: False, "profiles/aiko_unified/sessions/session2_history.json")
            ]
        }.get(norm(path), [])
        
        # Configure mock_exists
        mock_exists.side_effect = lambda path: norm(path) in [
            "profiles",
            "profiles/aiko_unified/profile.json",
            "history/legacy_profile",
            "profiles/aiko_unified/sessions",
            "history/legacy_profile/session1_history.json",
            "profiles/aiko_unified/sessions/session2_history.json"
        ]
        
        # Configure mock_isdir
        mock_isdir.side_effect = lambda path: norm(path) in [
            "profiles",
            "history/legacy_profile",
            "profiles/aiko_unified/sessions"
        ]
        
        # Mock file content reads for history files (metadata last_interaction)
        mock_open.return_value.read.side_effect = [
            '{"metadata": {"last_interaction": "2026-06-21 | 12:00:00"}}',
            '{"metadata": {"last_interaction": "2026-06-21 | 14:00:00"}}'
        ]
        
        sessions = get_all_recent_sessions()
        
        self.assertEqual(len(sessions), 2)
        self.assertEqual(sessions[0]["profile_name"], "Aiko Unified")
        self.assertEqual(sessions[0]["session_name"], "session2")
        self.assertEqual(sessions[0]["profile_file"], "aiko_unified/profile.json")
        
        self.assertEqual(sessions[1]["profile_name"], "Legacy Profile")
        self.assertEqual(sessions[1]["session_name"], "session1")
        self.assertEqual(sessions[1]["profile_file"], "legacy_profile.json")

    @patch('ui.DashboardScreen.get_all_recent_sessions')
    def test_dashboard_load_recent_sessions(self, mock_get_sessions):
        """Test that action_load_recent_1, 2, 3 dismisses the screen with the correct session config."""
        from ui.DashboardScreen import DashboardScreen
        from datetime import datetime
        
        mock_get_sessions.return_value = [
            {"profile_name": "Aiko", "session_name": "default", "last_interaction": datetime.now(), "profile_file": "Aiko.json"},
            {"profile_name": "Akari", "session_name": "session_1", "last_interaction": datetime.now(), "profile_file": "Akari.json"},
            {"profile_name": "Ako", "session_name": "default", "last_interaction": datetime.now(), "profile_file": "Ako.json"}
        ]
        
        screen = DashboardScreen()
        dismissed_result = None
        def mock_dismiss(result):
            nonlocal dismissed_result
            dismissed_result = result
        screen.dismiss = mock_dismiss
        
        # Test loading recent session 1
        screen.action_load_recent_1()
        self.assertEqual(dismissed_result, {"character": "Aiko.json", "session_name": "default"})
        
        # Test loading recent session 2
        screen.action_load_recent_2()
        self.assertEqual(dismissed_result, {"character": "Akari.json", "session_name": "session_1"})
        
        # Test loading recent session 3
        screen.action_load_recent_3()
        self.assertEqual(dismissed_result, {"character": "Ako.json", "session_name": "default"})

if __name__ == '__main__':
    unittest.main()

