import unittest
from unittest.mock import patch, MagicMock
import sys
import os

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.SettingsScreen import SettingsScreen

class TestSettingsScreen(unittest.TestCase):
    def setUp(self):
        # Backup global settings file to prevent test pollution
        from engines.config import SETTINGS_FILE
        self.backup_path = SETTINGS_FILE + ".bak"
        if os.path.exists(SETTINGS_FILE):
            os.rename(SETTINGS_FILE, self.backup_path)

        self.screen = SettingsScreen()
        self.screen.dismiss = MagicMock()
        self.screen.show_error = MagicMock()

        # Create mock widgets
        self.widgets = {
            "#remote_llm_url": MagicMock(value=""),
            "#remote_tts_url": MagicMock(value=""),
            "#memory_limit": MagicMock(value="15"),
            "#repetition_penalty": MagicMock(value="1.15"),
            "#tts_rate": MagicMock(value="170"),
            "#overhaul_candidate_count": MagicMock(value="2"),
            "#interaction_mode": MagicMock(value="rp"),
            "#clear_on_start": MagicMock(value=False),
            "#auto_recap_on_start": MagicMock(value=True),
            "#image_protocol": MagicMock(value="auto"),
            "#suppress_errors": MagicMock(value=True),
            "#default_llm_model": MagicMock(value="fluffy/l3-8b-stheno-v3.2"),
            "#summarizer_model": MagicMock(value="gemma2:2b"),
            "#local_utility_model": MagicMock(value="phi3"),
            "#tts_enabled": MagicMock(value=False),
            "#character_speak": MagicMock(value=True),
            "#speak_narration": MagicMock(value=True),
            "#default_tts_engine": MagicMock(value="edge-tts"),
            "#default_tts_voice": MagicMock(value="en-GB-SoniaNeural"),
            "#narration_tts_voice": MagicMock(value="en-US-AndrewNeural"),
            "#show_tts_engine": MagicMock(value=True),
            "#privacy_mode": MagicMock(value=False),
            "#debug_mode": MagicMock(value=False),
            "#execute_command": MagicMock(value=False),
            "#overhaul_pipeline_enabled": MagicMock(value=True),
            "#overhaul_instrumentation_enabled": MagicMock(value=True),
            "#overhaul_state_enabled": MagicMock(value=True),
            "#overhaul_memory_enabled": MagicMock(value=True),
            "#overhaul_planner_enabled": MagicMock(value=True),
            "#overhaul_candidates_enabled": MagicMock(value=False),
            "#overhaul_critic_enabled": MagicMock(value=False),
            "#overhaul_style_profile": MagicMock(value="balanced"),
            "#settings_error": MagicMock()
        }

        def mock_query_one(selector, type_cls=None):
            if selector in self.widgets:
                return self.widgets[selector]
            raise KeyError(f"Mock widget not found: {selector}")

        self.screen.query_one = mock_query_one

    def tearDown(self):
        # Restore global settings file
        from engines.config import SETTINGS_FILE
        if os.path.exists(SETTINGS_FILE):
            os.remove(SETTINGS_FILE)
        if os.path.exists(self.backup_path):
            os.rename(self.backup_path, SETTINGS_FILE)

    def test_cancel_action(self):
        """Test that cancel action dismisses with None."""
        self.screen.action_cancel()
        self.screen.dismiss.assert_called_once_with(None)

    @patch('engines.config.update_settings')
    def test_save_action_success(self, mock_update):
        """Test that saving with valid settings updates config and dismisses screen."""
        mock_update.return_value = True
        self.screen.action_save()

        # Verify update_settings was called
        self.assertTrue(mock_update.called)
        # Verify dismissed with settings dict
        self.screen.dismiss.assert_called_once()
        dismissed_dict = self.screen.dismiss.call_args[0][0]
        self.assertEqual(dismissed_dict["memory_limit"], 15)
        self.assertEqual(dismissed_dict["repetition_penalty"], 1.15)
        self.assertEqual(dismissed_dict["tts_rate"], 170)
        self.assertEqual(dismissed_dict["overhaul_candidate_count"], 2)
        self.assertEqual(dismissed_dict["interaction_mode"], "rp")

    @patch('engines.config.update_settings')
    def test_save_action_insecure_llm_url(self, mock_update):
        """Test validation rejects insecure HTTP remote LLM URL."""
        self.widgets["#remote_llm_url"].value = "http://insecure-llm.com"
        self.screen.action_save()

        self.screen.show_error.assert_called_once_with("Remote LLM URL must use secure HTTPS protocol.")
        mock_update.assert_not_called()
        self.screen.dismiss.assert_not_called()

    @patch('engines.config.update_settings')
    def test_save_action_insecure_tts_url(self, mock_update):
        """Test validation rejects insecure HTTP remote TTS URL."""
        self.widgets["#remote_tts_url"].value = "http://insecure-tts.com"
        self.screen.action_save()

        self.screen.show_error.assert_called_once_with("Remote TTS URL must use secure HTTPS protocol.")
        mock_update.assert_not_called()
        self.screen.dismiss.assert_not_called()

    @patch('engines.config.update_settings')
    def test_save_action_secure_urls_succeed(self, mock_update):
        """Test validation accepts secure HTTPS remote URLs."""
        mock_update.return_value = True
        self.widgets["#remote_llm_url"].value = "https://secure-llm.com"
        self.widgets["#remote_tts_url"].value = "https://secure-tts.com"
        self.screen.action_save()

        self.screen.show_error.assert_not_called()
        self.assertTrue(mock_update.called)
        self.screen.dismiss.assert_called_once()

    @patch('engines.config.update_settings')
    def test_save_action_numeric_validation_failures(self, mock_update):
        """Test that invalid numeric inputs trigger validation errors and do not save."""
        # 1. Invalid memory limit
        self.widgets["#memory_limit"].value = "not-an-int"
        self.screen.action_save()
        self.screen.show_error.assert_called_with("Memory Message Limit must be a positive integer.")
        self.screen.dismiss.assert_not_called()
        mock_update.assert_not_called()
        self.screen.show_error.reset_mock()

        # Reset memory limit to valid, test invalid repetition penalty
        self.widgets["#memory_limit"].value = "15"
        self.widgets["#repetition_penalty"].value = "not-a-float"
        self.screen.action_save()
        self.screen.show_error.assert_called_with("Repetition Penalty must be a positive number.")
        self.screen.dismiss.assert_not_called()
        mock_update.assert_not_called()
        self.screen.show_error.reset_mock()

        # Reset repetition penalty, test invalid tts rate
        self.widgets["#repetition_penalty"].value = "1.15"
        self.widgets["#tts_rate"].value = "invalid-int"
        self.screen.action_save()
        self.screen.show_error.assert_called_with("TTS Speech Rate must be a positive integer.")
        self.screen.dismiss.assert_not_called()
        mock_update.assert_not_called()
        self.screen.show_error.reset_mock()

        # Reset tts rate, test invalid overhaul candidate count
        self.widgets["#tts_rate"].value = "170"
        self.widgets["#overhaul_candidate_count"].value = "invalid"
        self.screen.action_save()
        self.screen.show_error.assert_called_with("Overhaul Candidate Count must be a positive integer.")
        self.screen.dismiss.assert_not_called()
        mock_update.assert_not_called()

    def test_button_pressed_cancel(self):
        """Test that pressing the cancel button triggers cancel action."""
        event = MagicMock()
        event.button.id = "btn_cancel"
        with patch.object(self.screen, 'action_cancel') as mock_cancel:
            self.screen.on_button_pressed(event)
            mock_cancel.assert_called_once()

    def test_button_pressed_save(self):
        """Test that pressing the save button triggers save action."""
        event = MagicMock()
        event.button.id = "btn_save"
        with patch.object(self.screen, 'action_save') as mock_save:
            self.screen.on_button_pressed(event)
            mock_save.assert_called_once()

    def test_show_error(self):
        """Test show_error method correctly updates and displays error label."""
        # Restore real method behavior for show_error but mock query_one
        self.screen.show_error = SettingsScreen.show_error.__get__(self.screen, SettingsScreen)
        mock_err_label = MagicMock()
        self.widgets["#settings_error"] = mock_err_label

        self.screen.show_error("Validation error message")
        mock_err_label.update.assert_called_once_with("Validation error message")
        self.assertTrue(mock_err_label.display)

if __name__ == '__main__':
    unittest.main()
