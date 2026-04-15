import unittest
import os
import sys
import re # Import re
from unittest.mock import patch, MagicMock
from io import StringIO
from colorama import Fore, Style # Import Fore and Style

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import app_commands and its dependencies (memory_manager, get_setting) at the top level
from engines.app_commands import app_commands, RestartRequested, RegenerateRequested
from engines.memory_v2 import memory_manager
from engines.config import get_setting

def strip_ansi(text):
    """Helper to strip ANSI escape codes for testing."""
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)

class TestAppCommands(unittest.TestCase):

    def setUp(self):
        # Create a dummy history directory for testing
        self.test_history_dir = "test_app_commands_history"
        os.makedirs(self.test_history_dir, exist_ok=True)

        # Patch HISTORY_PATH in app_commands to use our test directory
        self.patcher_history_path = patch('engines.app_commands.HISTORY_PATH', self.test_history_dir)
        self.patcher_history_path.start()

        # Patch memory_manager as it's used directly in app_commands
        self.patcher_memory_manager = patch('engines.app_commands.memory_manager', spec=memory_manager)
        self.mock_memory_manager = self.patcher_memory_manager.start()

        # Patch get_setting as it's used directly in app_commands
        self.patcher_get_setting = patch('engines.app_commands.get_setting')
        self.mock_get_setting = self.patcher_get_setting.start()


    def tearDown(self):
        # Clean up the dummy history directory
        if os.path.exists(self.test_history_dir):
            import shutil
            shutil.rmtree(self.test_history_dir)
        self.patcher_history_path.stop()
        self.patcher_memory_manager.stop()
        self.patcher_get_setting.stop()


    @patch('sys.stdout', new_callable=StringIO)
    def test_history_no_profile_active(self, mock_stdout):
        self.mock_get_setting.return_value = None # Mock current_character_profile to be None
        
        result = app_commands("//history")
        self.assertTrue(result) # Command was handled
        self.assertIn("[SYSTEM] No character profile active. Cannot display history.", strip_ansi(mock_stdout.getvalue()))

    @patch('sys.stdout', new_callable=StringIO)
    def test_history_no_history_found(self, mock_stdout):
        self.mock_get_setting.return_value = "TestProfile.json" # Mock current_character_profile
        self.mock_memory_manager.load_history.return_value = []

        result = app_commands("//history")
        self.assertTrue(result)
        self.assertIn("[SYSTEM] No history found for the current profile.", strip_ansi(mock_stdout.getvalue()))
        self.mock_memory_manager.load_history.assert_called_with("TestProfile", limit=15)

    @patch('sys.stdout', new_callable=StringIO)
    def test_history_with_history_found(self, mock_stdout):
        self.mock_get_setting.return_value = "TestProfile.json" # Mock current_character_profile
        self.mock_memory_manager.load_history.return_value = [
            {"role": "user", "content": "Hello there!"},
            {"role": "assistant", "content": "Hi, how can I help?"}
        ]

        result = app_commands("//history")
        self.assertTrue(result)
        self.mock_memory_manager.load_history.assert_called_with("TestProfile", limit=15)
        
        output = strip_ansi(mock_stdout.getvalue())
        self.assertIn("=== Past Conversation ===", output)
        self.assertIn("User: Hello there!", output)
        self.assertIn("Assistant: Hi, how can I help?", output)
        self.assertIn("=========================", output)

    @patch('sys.stdout', new_callable=StringIO)
    def test_restart_raises_and_prints_message(self, mock_stdout):
        with self.assertRaises(RestartRequested):
            app_commands("//restart")
        output = strip_ansi(mock_stdout.getvalue())
        self.assertIn("[SYSTEM] Restarting application...", output)
        # Ensure no extra leftover lines bleed in after the raise
        lines = [l for l in output.splitlines() if l.strip()]
        self.assertEqual(len(lines), 1)

    @patch('sys.stdout', new_callable=StringIO)
    def test_recap_alias_works(self, mock_stdout):
        self.mock_get_setting.return_value = "TestProfile.json" # Mock current_character_profile
        self.mock_memory_manager.load_history.return_value = [
            {"role": "user", "content": "Hello there!"}
        ]
        
        result = app_commands("//recap")
        self.assertTrue(result)
        self.mock_memory_manager.load_history.assert_called_with("TestProfile", limit=15)
        output = strip_ansi(mock_stdout.getvalue())
        self.assertIn("User: Hello there!", output)

    def test_regen_commands_propagate_in_tui_mode(self):
        for cmd in ("//regen", "//regenerate"):
            with self.subTest(cmd=cmd):
                with self.assertRaises(RegenerateRequested):
                    app_commands(cmd, suppress_output=True)


    @patch('sys.stdout', new_callable=StringIO)
    def test_toggle_errors_enables_suppression(self, mock_stdout):
        # Start with suppress_errors = False → toggling should enable it
        self.mock_get_setting.return_value = False
        result = app_commands("//toggle_errors")
        self.assertTrue(result)
        output = strip_ansi(mock_stdout.getvalue())
        self.assertIn("[SYSTEM] Non-critical error messages suppressed.", output)

    @patch('sys.stdout', new_callable=StringIO)
    def test_toggle_errors_disables_suppression(self, mock_stdout):
        # Start with suppress_errors = True → toggling should disable it
        self.mock_get_setting.return_value = True
        result = app_commands("//toggle_errors")
        self.assertTrue(result)
        output = strip_ansi(mock_stdout.getvalue())
        self.assertIn("[SYSTEM] Error messages will now be shown.", output)


if __name__ == "__main__":
    unittest.main()

